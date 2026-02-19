package main

import (
	"crypto/rand"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"

	"gopkg.in/macaroon.v2"
)

var (
	lndREST     = "https://mycelia.m.voltageapp.io:8080"
	macaroonHex string
	rootKey     []byte
)

type Route struct {
	Backend string
	Price   int64
}

var routes = map[string]Route{
	"/oracle/btcusd":      {Backend: "http://127.0.0.1:9100", Price: 10},
	"/oracle/btcusd/vwap": {Backend: "http://127.0.0.1:9101", Price: 20},
	"/oracle/ethusd":      {Backend: "http://127.0.0.1:9102", Price: 10},
	"/oracle/eurusd":      {Backend: "http://127.0.0.1:9103", Price: 10},
	"/oracle/xauusd":      {Backend: "http://127.0.0.1:9105", Price: 10},
	"/oracle/btceur":      {Backend: "http://127.0.0.1:9106", Price: 10},
}

var freeRoutes = map[string]string{
	"/health":                    "http://127.0.0.1:9100",
	"/oracle/status":             "http://127.0.0.1:9100",
	"/dlc/oracle/pubkey":         "http://127.0.0.1:9104",
	"/dlc/oracle/announcements":  "http://127.0.0.1:9104",
	"/dlc/oracle/status":         "http://127.0.0.1:9104",
}

// Prefix routes: paid endpoints with path prefix matching
type PrefixRoute struct {
	Prefix  string
	Backend string
	Price   int64
}

var prefixRoutes = []PrefixRoute{
	{Prefix: "/dlc/oracle/attestations/", Backend: "http://127.0.0.1:9104", Price: 1000},
}

type InvoiceResp struct {
	PaymentRequest string `json:"payment_request"`
	RHash          string `json:"r_hash"`
}

func createInvoice(amountSats int64, memo string) (string, []byte, error) {
	body := fmt.Sprintf(`{"value":"%d","memo":"%s"}`, amountSats, memo)
	req, _ := http.NewRequest("POST", lndREST+"/v1/invoices", strings.NewReader(body))
	req.Header.Set("Grpc-Metadata-macaroon", macaroonHex)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Transport: &http.Transport{
		TLSClientConfig: &tls.Config{},
	}}
	resp, err := client.Do(req)
	if err != nil {
		return "", nil, err
	}
	defer resp.Body.Close()

	var inv InvoiceResp
	json.NewDecoder(resp.Body).Decode(&inv)
	rHash, _ := base64.StdEncoding.DecodeString(inv.RHash)
	return inv.PaymentRequest, rHash, nil
}

func mintMacaroon(paymentHash []byte) (*macaroon.Macaroon, error) {
	// L402 identifier: version (2) + payment_hash (32) + token_id (32) = 66 bytes
	id := make([]byte, 66)
	binary.BigEndian.PutUint16(id[:2], 0) // L402 version 0
	copy(id[2:34], paymentHash)
	rand.Read(id[34:66]) // random token ID
	mac, err := macaroon.New(rootKey, id, "slo", macaroon.LatestVersion)
	if err != nil {
		return nil, err
	}
	return mac, nil
}

func verifyL402(authHeader string) bool {
	parts := strings.SplitN(authHeader, " ", 2)
	if len(parts) != 2 {
		return false
	}
	tokenParts := strings.SplitN(parts[1], ":", 2)
	if len(tokenParts) != 2 {
		return false
	}
	macBytes, err := hex.DecodeString(tokenParts[0])
	if err != nil {
		macBytes, err = base64.StdEncoding.DecodeString(tokenParts[0])
		if err != nil {
			log.Printf("Auth: cannot decode macaroon: %v", err)
			return false
		}
	}
	mac := &macaroon.Macaroon{}
	if err := mac.UnmarshalBinary(macBytes); err != nil {
		return false
	}
	if err := mac.Verify(rootKey, func(caveat string) error { return nil }, nil); err != nil {
		log.Printf("Auth: verify error: %v", err)
		return false
	}
	log.Printf("Auth: verified OK")
	return true
}

func proxyTo(backendURL string, w http.ResponseWriter, r *http.Request) {
	target, _ := url.Parse(backendURL)
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.ServeHTTP(w, r)
}

func handler(w http.ResponseWriter, r *http.Request) {
	authStr := "-"; if r.Header.Get("Authorization") != "" { authStr = "auth" }; log.Printf("%s %s %s %s", r.RemoteAddr, r.Method, r.URL.Path, authStr)
	path := r.URL.Path

	if backend, ok := freeRoutes[path]; ok {
		proxyTo(backend, w, r)
		return
	}

	route, ok := routes[path]
	if !ok {
		// Check prefix routes
		for _, pr := range prefixRoutes {
			if strings.HasPrefix(path, pr.Prefix) {
				route = Route{Backend: pr.Backend, Price: pr.Price}
				ok = true
				break
			}
		}
		if !ok {
			http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
			return
		}
	}

	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "L402 ") || strings.HasPrefix(auth, "LSAT ") {
		if verifyL402(auth) {
			proxyTo(route.Backend, w, r)
			return
		}
		http.Error(w, `{"error":"invalid token"}`, http.StatusUnauthorized)
		return
	}

	payReq, rHash, err := createInvoice(route.Price, "SLO "+path)
	if err != nil {
		log.Printf("Invoice error: %v", err)
		http.Error(w, `{"error":"invoice creation failed"}`, http.StatusInternalServerError)
		return
	}

	mac, err := mintMacaroon(rHash)
	if err != nil {
		log.Printf("Macaroon error: %v", err)
		http.Error(w, `{"error":"macaroon creation failed"}`, http.StatusInternalServerError)
		return
	}

	macBytes, _ := mac.MarshalBinary()
	macB64 := base64.StdEncoding.EncodeToString(macBytes)

	w.Header().Set("WWW-Authenticate", fmt.Sprintf(`L402 macaroon="%s", invoice="%s"`, macB64, payReq))
	w.WriteHeader(http.StatusPaymentRequired)
	w.Write([]byte("Payment Required"))
}

func main() {
	macData, err := os.ReadFile("/home/jonathan_bulkeley/slo/creds/admin.macaroon")
	if err != nil {
		log.Fatal("Failed to read macaroon:", err)
	}
	macaroonHex = hex.EncodeToString(macData)

	rootKeyPath := "/home/jonathan_bulkeley/slo/creds/l402_root_key.bin"
	rootKey, err = os.ReadFile(rootKeyPath)
	if err != nil || len(rootKey) != 32 {
		rootKey = make([]byte, 32)
		rand.Read(rootKey)
		os.WriteFile(rootKeyPath, rootKey, 0600)
		log.Println("Generated new L402 root key")
	} else {
		log.Println("Loaded existing L402 root key")
	}

	log.Println("SLO L402 Proxy starting on :8080")
	log.Fatal(http.ListenAndServe(":8080", http.HandlerFunc(handler)))
}

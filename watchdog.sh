#!/bin/bash
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M:%S') [watchdog]"

check_endpoint() {
    local name="$1"
    local url="$2"
    local service="$3"
    
    response=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$response" = "200" ] || [ "$response" = "402" ]; then
        echo "$LOG_PREFIX $name OK ($response)"
    else
        echo "$LOG_PREFIX $name FAILED (HTTP $response) - restarting $service"
        sudo systemctl restart "$service"
        sleep 3
        response2=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url")
        if [ "$response2" = "200" ] || [ "$response2" = "402" ]; then
            echo "$LOG_PREFIX $name RECOVERED after restart ($response2)"
        else
            echo "$LOG_PREFIX $name STILL DOWN after restart ($response2) - ALERT"
        fi
    fi
}

echo "$LOG_PREFIX --- Starting watchdog check ---"
check_endpoint "L402-Proxy" "http://localhost:8080/health" "slo-l402-proxy"
check_endpoint "BTCUSD" "http://localhost:8080/oracle/btcusd" "slo-spot"
check_endpoint "BTCEUR" "http://localhost:8080/oracle/btceur" "slo-btceur"
check_endpoint "ETHUSD" "http://localhost:8080/oracle/ethusd" "slo-ethusd"
check_endpoint "EURUSD" "http://localhost:8080/oracle/eurusd" "slo-eurusd"
check_endpoint "XAUUSD" "http://localhost:8080/oracle/xauusd" "slo-xauusd"
check_endpoint "VWAP"   "http://localhost:8080/oracle/btcusd/vwap"   "slo-vwap"
check_endpoint "DLC-Pubkey" "http://localhost:8080/dlc/oracle/pubkey" "slo-dlc-server"
check_endpoint "DLC-Announce" "http://localhost:8080/dlc/oracle/announcements" "slo-dlc-scheduler"
echo "$LOG_PREFIX --- Watchdog check complete ---"

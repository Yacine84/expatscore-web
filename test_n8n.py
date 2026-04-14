#!/usr/bin/env python3
"""
test_n8n.py
Production-ready client for ExpatScore.de n8n Webhook integration.
 Sends Reddit data to n8n AI Agent (Groq/Llama 3.3).
"""

import requests
import json
import sys
from typing import Dict

# ============================================================================
# CONFIGURATION - Updated for MacBook Pro Docker Setup
# ============================================================================
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/reddit-lead"
# Note: Using /webhook-test/ path for testing with n8n editor open on MacBook

# Timeout configuration (seconds) - Optimized for local Docker
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

# ============================================================================
# MAIN SCRIPT
# ============================================================================

def send_to_n8n(payload: Dict, webhook_url: str = N8N_WEBHOOK_URL) -> bool:
    """
    Sends JSON payload to n8n webhook with robust error handling.
    
    Args:
        payload: Dictionary containing message and source data
        webhook_url: n8n webhook endpoint URL
        
    Returns:
        bool: True if successful, False if failed
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ExpatScore-RedditBot/1.0"
    }
    
    print(f"📤 Sending to n8n: {webhook_url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            url=webhook_url,
            json=payload,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
        )
        
        # Handle HTTP responses
        if response.status_code == 200:
            print(f"✅ Success! Status Code: {response.status_code}")
            try:
                response_data = response.json()
                print(f"📨 n8n Response: {json.dumps(response_data, indent=2)}")
            except ValueError:
                print(f"📨 Response (non-JSON): {response.text[:200]}")
            return True
            
        elif response.status_code == 404:
            print(f"❌ Error 404: Webhook not found.")
            print("💡 Ensure the n8n workflow is active and the webhook node listens to POST /reddit-lead")
            return False
            
        elif response.status_code == 401:
            print(f"❌ Error 401: Unauthorized. Check n8n basic auth settings.")
            return False
            
        else:
            print(f"⚠️ HTTP Error: Status Code {response.status_code}")
            print(f"📄 Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectTimeout:
        print(f"⏱️ Error: Connection timeout after {CONNECT_TIMEOUT}s")
        print("💡 Check if Docker n8n is running: docker ps")
        return False
        
    except requests.exceptions.ReadTimeout:
        print(f"⏱️ Error: Read timeout after {READ_TIMEOUT}s")
        print("💡 n8n processing is taking too long. Check AI node configuration.")
        return False
        
    except requests.exceptions.ConnectionError:
        print(f"🔌 Error: Connection refused to {webhook_url}")
        print("💡 Troubleshooting for MacBook + Docker:")
        print("   1. Verify n8n is running: docker-compose ps")
        print("   2. Check port mapping: docker port n8n_expatscore")
        print("   3. Ensure you're using 'localhost' (MacBook host) not container name")
        return False
        
    except requests.exceptions.InvalidURL:
        print(f"🔗 Error: Invalid URL format '{webhook_url}'")
        return False
        
    except Exception as e:
        print(f"💥 Unexpected Error: {type(e).__name__}: {str(e)}")
        return False


def main():
    """Main execution with Reddit bot test payload."""
    
    print("🚀 ExpatScore.de - Reddit Bot to n8n Connector")
    print("=" * 50)
    print(f"🐳 Target: Docker n8n on MacBook Pro")
    print("-" * 50)
    
    # Payload structure as requested
    reddit_payload = {
        "message": "Hello from Yassine's Reddit Bot",
        "source": "reddit"
    }
    
    # Execute send
    success = send_to_n8n(reddit_payload)
    
    if success:
        print("\n🎉 Webhook test successful! Reddit → n8n pipeline is live.")
        sys.exit(0)
    else:
        print("\n💔 Test failed. Fix errors above and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
Example Python client for the Image Search Flask API
Demonstrates how to crawl a website and search for images programmatically
"""
import requests
import json
import time
import sseclient  # pip install sseclient-py

BASE_URL = "http://127.0.0.1:5000"

class ImageSearchClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session_id = None
        self.chat_history = []
    
    def start_crawl(self, url, limit=10):
        """Start crawling a website"""
        print(f"🕷️ Starting crawl of {url} (limit: {limit} pages)...")
        
        response = requests.post(
            f"{self.base_url}/crawl",
            json={"url": url, "limit": limit}
        )
        response.raise_for_status()
        
        data = response.json()
        self.session_id = data["session_id"]
        print(f"✅ Crawl started. Session ID: {self.session_id}")
        
        return self.session_id
    
    def monitor_crawl_progress(self):
        """Monitor crawl progress via Server-Sent Events"""
        if not self.session_id:
            raise ValueError("No active session. Start a crawl first.")
        
        print("📡 Monitoring crawl progress...")
        
        # Use SSE client to receive real-time updates
        response = requests.get(
            f"{self.base_url}/crawl/{self.session_id}/status",
            stream=True
        )
        
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            data = json.loads(event.data)
            
            if data["type"] == "status":
                print(f"📊 Status: {data['data']['message']}")
            
            elif data["type"] == "progress":
                print(f"⚡ Progress: {data['data']['message']}")
                if "stats" in data["data"]:
                    formats = data["data"]["stats"]["formats"]
                    print(f"   Formats: {formats}")
            
            elif data["type"] == "completed":
                print(f"✅ Crawl completed!")
                print(f"   Total images: {data['data']['total_images']}")
                print(f"   Total pages: {data['data']['total_pages']}")
                
                # Initialize chat with the summary
                self.chat_history = [{
                    "role": "ai",
                    "content": data["data"]["summary"]
                }]
                print(f"\n🤖 AI: {data['data']['summary']}")
                
                return True
            
            elif data["type"] == "error":
                print(f"❌ Error: {data['data']['message']}")
                return False
    
    def search_images(self, query):
        """Search for images using natural language"""
        if not self.session_id:
            raise ValueError("No active session. Start a crawl first.")
        
        # Add human message to history
        self.chat_history.append({
            "role": "human",
            "content": query
        })
        
        print(f"\n👤 You: {query}")
        print("🔍 Searching...")
        
        response = requests.post(
            f"{self.base_url}/chat",
            json={
                "session_id": self.session_id,
                "chat_history": self.chat_history
            }
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Add AI response to history
        self.chat_history.append({
            "role": "ai",
            "content": data["response"]
        })
        
        print(f"\n🤖 AI: {data['response']}")
        
        # Return search results for programmatic use
        return data.get("search_results", [])
    
    def list_sessions(self):
        """List all crawl sessions"""
        response = requests.get(f"{self.base_url}/sessions")
        response.raise_for_status()
        return response.json()["sessions"]
    
    def interactive_search(self):
        """Interactive search mode"""
        print("\n💬 Interactive search mode. Type 'quit' to exit.")
        
        while True:
            query = input("\n👤 You: ").strip()
            
            if query.lower() in ['quit', 'exit']:
                print("👋 Goodbye!")
                break
            
            if not query:
                continue
            
            try:
                results = self.search_images(query)
                
                # Optionally process results programmatically
                if results:
                    print(f"\n📊 Found {len(results)} images (raw data available)")
                    
            except Exception as e:
                print(f"❌ Error: {e}")


def main():
    """Example usage"""
    # Initialize client
    client = ImageSearchClient()
    
    # Example 1: Crawl and search programmatically
    print("=== Example 1: Programmatic Usage ===")
    
    # Start crawl
    url = "https://www.apple.com/iphone"
    session_id = client.start_crawl(url, limit=5)
    
    # Monitor progress
    success = client.monitor_crawl_progress()
    
    if success:
        # Search for images
        results = client.search_images("Show me iPhone camera images")
        
        # Process results programmatically
        print("\n📊 Raw search results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['alt_text']}")
            print(f"   Format: {result['format'].upper()}")
            print(f"   URL: {result['url']}")
            print(f"   Score: {result['score']:.4f}")
    
    # Example 2: Interactive mode
    print("\n\n=== Example 2: Interactive Mode ===")
    client.interactive_search()
    
    # Example 3: List all sessions
    print("\n\n=== Example 3: List Sessions ===")
    sessions = client.list_sessions()
    print(f"Found {len(sessions)} sessions:")
    for session in sessions:
        print(f"- {session['url']} ({session['status']}) - {session['total_images']} images")


if __name__ == "__main__":
    # Make sure the Flask server is running before executing this
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print("✅ Server is running\n")
        
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Flask server is not running.")
        print("Please start the server with: python flask_server.py") 
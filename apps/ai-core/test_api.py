import requests
import json

def test_api():
    base_url = "http://localhost:8000"
    
    # Test cases
    test_cases = [
        {
            "name": "Training job with low temp and memory",
            "data": {"gpu_temp": 45, "gpu_mem_used": 256, "job_type": "training"},
            "expected": "Should be good placement (temp < 75, memory < 20000)"
        },
        {
            "name": "Training job with high temp",
            "data": {"gpu_temp": 80, "gpu_mem_used": 256, "job_type": "training"},
            "expected": "Should be bad placement (temp > 75 for training)"
        },
        {
            "name": "Inference job with high temp",
            "data": {"gpu_temp": 80, "gpu_mem_used": 256, "job_type": "inference"},
            "expected": "Should be good placement (temp < 85 for inference)"
        },
        {
            "name": "Training job with high memory usage",
            "data": {"gpu_temp": 45, "gpu_mem_used": 22000, "job_type": "training"},
            "expected": "Should be bad placement (memory > 20000)"
        }
    ]
    
    print("Testing AI Core API...")
    print("=" * 50)
    
    for test in test_cases:
        try:
            response = requests.post(f"{base_url}/predict", json=test["data"])
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {test['name']}")
                print(f"   Input: {test['data']}")
                print(f"   Prediction: {result}")
                print(f"   Expected: {test['expected']}")
                print()
            else:
                print(f"❌ {test['name']} - HTTP {response.status_code}")
                print(f"   Error: {response.text}")
                print()
        except requests.exceptions.ConnectionError:
            print(f"❌ {test['name']} - Connection Error")
            print("   Make sure the FastAPI service is running on port 8000")
            print()
            break
        except Exception as e:
            print(f"❌ {test['name']} - Error: {e}")
            print()

if __name__ == "__main__":
    test_api()

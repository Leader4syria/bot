from pyngrok import ngrok

try:
    tunnels = ngrok.get_tunnels()
    if tunnels:
        for tunnel in tunnels:
            print(tunnel)
    else:
        print("No active ngrok tunnels found.")
except Exception as e:
    print(f"An error occurred: {e}")

import numpy as np
import random

# Constants
alpha = 4  # Path loss exponent
N0 = -174  # Noise spectral density in dBm/Hz
W = 10e6  # Bandwidth in Hz
default_Pt_d2d = 10  # D2D transmit power in dBm
default_Pt_infra = 20  # Infrastructure transmit power in dBm
default_d2d_threshold = 150  # Maximum distance for D2D communication (in meters)
default_self_interference_cancellation = 110  # in dB
base_station_ip = "192.168.1.1"  # Fixed IP for base station

# Generate random IPs
def generate_random_ip():
    return f"192.168.1.{random.randint(2, 254)}"

# Convert dBm to Watts
def dbm_to_watts(dBm):
    return 10 ** ((dBm - 30) / 10)

# SINR calculation
def calculate_sinr(Pt, d, cancellation=0):
    Pt_watts = dbm_to_watts(Pt)
    residual_interference = Pt_watts / (10 ** (cancellation / 10)) if cancellation else 0
    return Pt_watts / (d ** alpha * (dbm_to_watts(N0) + residual_interference))

# Throughput calculation
def calculate_throughput(Pt, d, cancellation=0):
    sinr = calculate_sinr(Pt, d, cancellation)
    return W * np.log2(1 + sinr)

# Simulate communication
def simulate_communication(dist_ab, dist_a_bs, dist_b_bs, params):
    if dist_ab <= params["d2d_threshold"]:
        # D2D Communication
        th_d2d = calculate_throughput(params["Pt_d2d"], dist_ab, params["self_interference_cancellation"])
        mode = "D2D"
        route = f"{node_a['ip']} ↔ {node_b['ip']}"
    else:
        # Infrastructure-based Communication
        th_a_to_bs = calculate_throughput(params["Pt_infra"], dist_a_bs)
        th_bs_to_b = calculate_throughput(params["Pt_infra"], dist_b_bs)
        th_d2d = min(th_a_to_bs, th_bs_to_b)  # Bottleneck throughput
        mode = "Base Station"
        route = f"{node_a['ip']} → {base_station_ip} → {node_b['ip']}"
    return th_d2d, mode, route

# Display results
def display_results(pos_a, pos_b, pos_bs, dist_ab, dist_a_bs, dist_b_bs, throughput, mode, route):
    print(f"\n--- Simulation Results ---")
    print(f"Position of Node A: {pos_a}")
    print(f"IP Address of Node A: {node_a['ip']}")
    print(f"Position of Node B: {pos_b}")
    print(f"IP Address of Node B: {node_b['ip']}")
    print(f"Position of Base Station: {pos_bs}")
    print(f"Base Station IP: {base_station_ip}")
    print(f"Distance A to B: {dist_ab:.2f} m")
    print(f"Distance A to Base Station: {dist_a_bs:.2f} m")
    print(f"Distance B to Base Station: {dist_b_bs:.2f} m")
    print(f"Communication Mode: {mode}")
    print(f"Achieved Throughput: {throughput:.2f} bps/Hz")
    print(f"Route: {route}")

# Main menu-driven function
def main():
    # Initialize parameters
    params = {
        "Pt_d2d": default_Pt_d2d,
        "Pt_infra": default_Pt_infra,
        "d2d_threshold": default_d2d_threshold,
        "self_interference_cancellation": default_self_interference_cancellation,
    }

    pos_bs = np.array([250, 250])  # Base station at the center
    pos_a = None
    pos_b = None
    global node_a, node_b
    node_a = {"ip": None}
    node_b = {"ip": None}

    while True:
        print("\n--- Menu ---")
        print("1. Add/Update Node A Position")
        print("2. Add/Update Node B Position")
        print("3. Adjust Parameters")
        print("4. Simulate Communication")
        print("5. Exit")

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            x, y = map(float, input("Enter position of Node A (x y): ").split())
            pos_a = np.array([x, y])
            node_a["ip"] = generate_random_ip()
            print(f"Node A position set to {pos_a} with IP {node_a['ip']}")

        elif choice == "2":
            x, y = map(float, input("Enter position of Node B (x y): ").split())
            pos_b = np.array([x, y])
            node_b["ip"] = generate_random_ip()
            print(f"Node B position set to {pos_b} with IP {node_b['ip']}")

        elif choice == "3":
            print("\n--- Adjust Parameters ---")
            print(f"Current D2D Transmit Power: {params['Pt_d2d']} dBm")
            print(f"Current Infrastructure Transmit Power: {params['Pt_infra']} dBm")
            print(f"Current D2D Threshold: {params['d2d_threshold']} m")
            print(f"Current Self-Interference Cancellation: {params['self_interference_cancellation']} dB")
            
            params["Pt_d2d"] = float(input("Enter new D2D Transmit Power (in dBm): ").strip())
            params["Pt_infra"] = float(input("Enter new Infrastructure Transmit Power (in dBm): ").strip())
            params["d2d_threshold"] = float(input("Enter new D2D Threshold (in meters): ").strip())
            params["self_interference_cancellation"] = float(input("Enter new Self-Interference Cancellation (in dB): ").strip())
            print("Parameters updated!")

        elif choice == "4":
            if pos_a is None or pos_b is None:
                print("Error: Please set positions for both Node A and Node B.")
                continue
            
            # Calculate distances
            dist_ab = np.linalg.norm(pos_a - pos_b)  # Distance between A and B
            dist_a_bs = np.linalg.norm(pos_a - pos_bs)  # Distance between A and Base Station
            dist_b_bs = np.linalg.norm(pos_b - pos_bs)  # Distance between B and Base Station

            # Run simulation
            throughput, mode, route = simulate_communication(dist_ab, dist_a_bs, dist_b_bs, params)

            # Display results
            display_results(pos_a, pos_b, pos_bs, dist_ab, dist_a_bs, dist_b_bs, throughput, mode, route)

        elif choice == "5":
            print("Exiting the program. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()

import hashlib
import hmac
import secrets
import subprocess
import curses

# ------------------------------------------------------------------------------

class CryptographicHelper:
    @staticmethod
    def generate_hash(data):
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def generate_hmac(key, data):
        return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def generate_nonce():
        return secrets.token_hex(16)

# ------------------------------------------------------------------------------

class NetworkHelper:
    assigned_ips = set()

    @staticmethod
    def assign_ip(entity_type):
        network_id_map = {
            "mn": "10.1.0",
            "fa": "192.168.2",
            "ha": "192.168.1"
        }

        if entity_type not in network_id_map:
            raise ValueError(f"Unknown entity type: {entity_type}")

        network_id = network_id_map[entity_type]

        # Generate a unique IP address
        while True:
            ip_address = f"{network_id}.{secrets.randbelow(255)}"
            if ip_address not in NetworkHelper.assigned_ips:
                NetworkHelper.assigned_ips.add(ip_address)
                print(f"Assigned IP {ip_address} to {entity_type}")
                return ip_address

    @staticmethod
    def release_ip(ip_address):
        """Releases an IP address, making it available for reassignment."""
        if ip_address in NetworkHelper.assigned_ips:
            NetworkHelper.assigned_ips.remove(ip_address)
            print(f"Released IP {ip_address}.")
        else:
            print(f"IP {ip_address} is not currently assigned.")

    @staticmethod
    def add_route(destination, gateway):
        try:
            command = ["sudo", "route", "-n", "add", destination, gateway] # For Mac
            # command = ["sudo", "ip", "route", "add", destination, "via", gateway] # For Linux
            subprocess.run(command, check=True)
            print(f"Successfully added route to {destination} via {gateway}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to add route: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    @staticmethod
    def remove_route(destination):
        """Remove a network route using the macOS 'route delete' command."""
        try:
            command = ["sudo", "route", "-n", "delete", destination] # For Mac
            # command = ["sudo", "ip", "route", "del", destination] # For Linux
            subprocess.run(command, check=True)
            print(f"Successfully removed route to {destination}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to remove route: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

# ------------------------------------------------------------------------------

class Registration:
    def __init__(self, request_type, target, data):
        self.request_type = request_type
        self.target = target
        self.data = data
        self.nonce = None

    def add_nonce(self, nonce):
        self.nonce = nonce

# ------------------------------------------------------------------------------

class MobileNode:
    def __init__(self, identity, home_agent):
        self.identity = identity
        self.shared_key_mn_ha = None
        self.temp_identity = None
        self.nonce_mn = CryptographicHelper.generate_nonce()
        self.coa = NetworkHelper.assign_ip("mn")
        self.home_agent = home_agent
        self.original_ha = home_agent
        
    def re_register_with_original_ha(self, fa):
        """Re-register the MN's new COA with the original HA."""
        request_data = {
            "temp_identity": self.temp_identity,
            "nonce_mn": self.nonce_mn,
            "coa": self.coa
        }
        print(f"Re-registering MN {self.identity} with original Home Agent {self.original_ha.identity}.")
        registration = Registration("re-registration", self.original_ha, request_data)
        return fa.handle_registration_request(self, self.original_ha, registration)

    def initiate_registration(self, ha, fa):
        self.temp_identity = CryptographicHelper.generate_hash(f"{self.identity}{self.nonce_mn}")
        request_data = {
            "temp_identity": self.temp_identity,
            "nonce_mn": self.nonce_mn,
            "coa": self.coa
        }
        registration = Registration("registration", ha, request_data)
        return fa.handle_registration_request(self, ha, registration)

    def move_to_new_network(self, ha, fa):
        print(f"MobileNode {self.identity} moving to a new Foreign Network.")
        self.coa = NetworkHelper.assign_ip("mn")
        self.home_agent = ha
        self.nonce_mn = CryptographicHelper.generate_nonce()
        self.temp_identity = CryptographicHelper.generate_hash(f"{self.identity}{self.nonce_mn}")

        request_data = {
            "temp_identity": self.temp_identity,
            "nonce_mn": self.nonce_mn,
            "coa": self.coa
        }
        registration = Registration("registration", ha, request_data)
        self.re_register_with_original_ha(fa)
        return fa.handle_registration_request(self, ha, registration)

# ------------------------------------------------------------------------------

class ForeignAgent:
    def __init__(self, identity, ip_address):
        self.identity = identity
        self.ip_address = ip_address if ip_address else NetworkHelper.assign_ip("fa")
        self.nonce_fa = CryptographicHelper.generate_nonce()

    def handle_registration_request(self, mn, ha, registration):
        registration.add_nonce(self.nonce_fa)
        return ha.process_registration(self, mn, registration)

# ------------------------------------------------------------------------------

class HomeAgent:
    def __init__(self, identity, ip_address):            
        self.identity = identity
        self.ip_address = ip_address if ip_address else NetworkHelper.assign_ip("ha")
        self.shared_key_mn_ha = "shared_secret_mn_ha"
        self.nonce_ha = CryptographicHelper.generate_nonce()
        self.bindings = {}
        self.peers = set()

    def process_registration(self, fa, mn, registration):
        temp_identity = registration.data["temp_identity"]
        if temp_identity == CryptographicHelper.generate_hash(f"{mn.identity}{registration.data['nonce_mn']}"):
            shared_key_mn_fa = CryptographicHelper.generate_hmac(
                self.shared_key_mn_ha,
                registration.data['nonce_mn'] + self.nonce_ha + fa.identity
            )
            binding = {
                "temp_identity": temp_identity,
                "shared_key_mn_fa": shared_key_mn_fa,
                "nonce_ha": self.nonce_ha,
                "coa": registration.data["coa"],
                "foreign_agent": fa.ip_address
            }
            self.bindings[mn.identity] = binding
            NetworkHelper.add_route(mn.coa, self.ip_address)
            return {"status": "success", "binding": self.bindings[mn.identity]}
        else:
            raise Exception("Invalid registration data")

# ------------------------------------------------------------------------------
        
def create_mesh_topology():
    """Establishes a mesh topology among all Home Agents."""
    print("\nCreating Mesh Topology Between Home Agents...")
    for ha_id, ha in ha_registry.items():
        ha.peers = set()
        for peer_id, peer_ha in ha_registry.items():
            if ha_id != peer_id:
                ha.peers.add(peer_id)
                print(f"HA {ha_id} (IP: {ha.ip_address}) connected to HA {peer_id} (IP: {peer_ha.ip_address})")
    print("Mesh topology created successfully.\n")
    
def print_mesh_topology():
    """Prints the mesh topology of the Home Agents."""
    if not ha_registry:
        print("No Home Agents in the network. Mesh topology is empty.")
        return

    print("\nMesh Topology of Home Agents:\n")
    
    ha_ids = list(ha_registry.keys())

    print("   ", end="")
    for ha_id in ha_ids:
        print(f"{ha_id:>8}", end="")
    print()

    for ha_id in ha_ids:
        print(f"{ha_id:<3}", end="")
        for peer_id in ha_ids:
            if peer_id in ha_registry[ha_id].peers:
                print(f"{'✓':>8}", end="")
            else:
                print(f"{' ':>8}", end="")
        print()

    print("\nLegend: ✓ indicates a connection between the Home Agents.\n")


# Global Registries
ha_registry = {
        "HA123": HomeAgent("HA123", ip_address="192.168.1.1"),
        "HA456": HomeAgent("HA456", ip_address="192.168.1.2"),
        "HA789": HomeAgent("HA789", ip_address="192.168.1.3"),
    }
fa_registry = {
        "FA123": ForeignAgent("FA123", ip_address="192.168.2.1"),
        "FA456": ForeignAgent("FA456", ip_address="192.168.2.2"),
        "FA789": ForeignAgent("FA789", ip_address="192.168.2.3"),
    }
mn_registry = {}

for ha in ha_registry.values():
    NetworkHelper.assigned_ips.add(ha.ip_address)

for fa in fa_registry.values():
    NetworkHelper.assigned_ips.add(fa.ip_address)

print("Initial assigned IPs:", NetworkHelper.assigned_ips)
create_mesh_topology()

# ------------------------------------------------------------------------------

def ping_mobile_node():
    """Simulate a ping from one mobile node to another."""
    source_id = input("Enter Source Mobile Node ID: ").strip()
    target_id = input("Enter Target Mobile Node's ID: ").strip()

    if source_id not in mn_registry:
        print(f"Error: Source Mobile Node {source_id} not found.")
        return

    if target_id not in mn_registry:
        print(f"Error: Target Mobile Node {target_id} not found.")
        return

    source = mn_registry[source_id]
    target = mn_registry[target_id]

    NetworkHelper.add_route(source.coa, target.coa)

    try:
        print(f"Pinging from Mobile Node {source_id} ({source.coa}) to {target_id} ({target.coa})...")
        command = ["ping", "-c", "4", target.coa]
        subprocess.run(command, check=True)
        print(f"Ping to {target_id} ({target.coa}) successful.")
    except subprocess.CalledProcessError as e:
        print(f"Ping failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def add_mobile_node():
    mn_id = input("Enter Mobile Node ID: ").strip()
    if mn_id in mn_registry:
        print("Error: MN already exists.")
        return

    ha_index = secrets.randbelow(len(ha_registry))
    ha_id, ha = list(ha_registry.items())[ha_index]
    fa_id, fa = list(fa_registry.items())[ha_index]

    if not fa:
        print(f"Error: No corresponding Foreign Agent found for Home Agent {ha_id}.")
        return

    print(f"Assigning Home Agent {ha_id}: {ha.ip_address} and corresponding Foreign Agent {fa_id}: {fa.ip_address} to MN {mn_id}.")

    mn = MobileNode(mn_id, ha)
    mn_registry[mn_id] = mn

    try:
        response = mn.initiate_registration(ha, fa)
        print(f"Registration Response: {response}")
    except Exception as e:
        print(f"Registration failed: {e}")

    print(f"Mobile Node {mn_id} created, registered, and assigned to network {ha_id}-{fa_id}.")
    
def add_network():
    ha_id = input("Enter Home Agent ID: ").strip()
    fa_id = input("Enter Foreign Agent ID: ").strip()

    ha_ip, fa_ip = NetworkHelper.assign_ip("ha"), NetworkHelper.assign_ip("fa")
    ha, fa = HomeAgent(ha_id, ha_ip), ForeignAgent(fa_id, fa_ip)
    ha_registry[ha_id], fa_registry[fa_id] = ha, fa

    create_mesh_topology()
    print(f"Added Home Agent {ha_id} with IP {ha_ip}.")
    print(f"Added Foreign Agent {fa_id} with IP {fa_ip}.")

def move_mobile_node():
    mn_id = input("Enter Mobile Node ID to move: ").strip()
    if mn_id not in mn_registry:
        print("Error: Mobile Node not found.")
        return

    mn = mn_registry[mn_id]
    current_ha = mn.home_agent
    print("\nCurrent Network Details:")
    print(f"  Home Agent: {current_ha.identity} (IP: {current_ha.ip_address})")
    print(f"  Care-of Address (COA): {mn.coa}\n")

    available_networks = [
        (ha_id, ha, fa_id, fa)
        for (ha_id, ha), (fa_id, fa) in zip(ha_registry.items(), fa_registry.items())
        if ha_id != current_ha.identity
    ]

    if not available_networks:
        print("No other networks available for movement.")
        return

    def network_selection_menu(stdscr):
        curses.curs_set(0)
        selected_index = 0

        while True:
            stdscr.clear()
            stdscr.addstr("Use Arrow Keys to navigate and press Enter to select:\n\n")

            for idx, (ha_id, ha, fa_id, fa) in enumerate(available_networks):
                if idx == selected_index:
                    stdscr.addstr(f"> Home Agent: {ha_id} (IP: {ha.ip_address}), Foreign Agent: {fa_id} (IP: {fa.ip_address})\n", curses.A_REVERSE)
                else:
                    stdscr.addstr(f"  Home Agent: {ha_id} (IP: {ha.ip_address}), Foreign Agent: {fa_id} (IP: {fa.ip_address})\n")

            key = stdscr.getch()

            if key == curses.KEY_UP and selected_index > 0:
                selected_index -= 1
            elif key == curses.KEY_DOWN and selected_index < len(available_networks) - 1:
                selected_index += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                return selected_index

    selected_index = curses.wrapper(network_selection_menu)

    new_ha_id, new_ha, new_fa_id, new_fa = available_networks[selected_index]
    print(f"\nMoving Mobile Node {mn_id} to new network:")
    print(f"  New Home Agent: {new_ha_id} (IP: {new_ha.ip_address})")
    print(f"  New Foreign Agent: {new_fa_id} (IP: {new_fa.ip_address})\n")

    response = mn.move_to_new_network(new_ha, new_fa)

    if mn_id in current_ha.bindings and current_ha != mn.original_ha:
        print(f"Removing binding for Mobile Node {mn_id} from old Home Agent {current_ha.identity}.")
        del current_ha.bindings[mn_id]
    else:
        print(f"Retaining binding for Mobile Node {mn_id} in the original Home Agent {current_ha.identity}.")


    if response.get("status") == "success":
        print(f"Mobile Node {mn_id} successfully moved to the new network.")
        print(f"New COA: {mn.coa}")
    else:
        print(f"Failed to move Mobile Node {mn_id}: {response.get('error', 'Unknown error')}")

def print_network():
    print("\n--- Local Network ---")
    if not ha_registry:
        print("No Home Agents registered.")
        return

    for ha_id, ha in ha_registry.items():
        print(f"{ha_id} (IP: {ha.ip_address}):")
        if ha.bindings:
            for mn_id, binding in ha.bindings.items():
                print(f"  MN {mn_id}: COA = {binding['coa']}")
        else:
            print("  No Mobile Nodes linked to this Home Agent.")

def menu():
    while True:
        print("\nMenu:")
        print("1. Add a Mobile Node (MN)")
        print("2. Add a new Network")
        print("3. Move a Mobile Node to a New Network")
        print("4. Print Registered Home Agents")
        print("5. Print Registered Foreign Agents")
        print("6. Print Registered Mobile Nodes")
        print("7. Show HA NAT Tables")
        print("8. Print Mesh Topology")
        print("9. Ping Mobile Node")
        print("10. Exit")

        choice = input("Enter your choice: ").strip()
        if choice == "1":
            add_mobile_node()
        elif choice == "2":
            add_network()
        elif choice == "3":
            move_mobile_node()
        elif choice == "4":
            print("Registered Home Agents:\n" + "\n".join(f"  {ha_id}: {ha.ip_address}" for ha_id, ha in ha_registry.items()))
        elif choice == "5":
            print("Registered Foreign Agents:\n" + "\n".join(f"  {fa_id}: {fa.ip_address}" for fa_id, fa in fa_registry.items()))
        elif choice == "6":
            print("Registered Mobile Nodes:\n" + "\n".join(f"  {mn_id}: {mn.coa}" for mn_id, mn in mn_registry.items()))
        elif choice == "7":
            print_network()
        elif choice == "8":
            print_mesh_topology()
        elif choice == "9":
            ping_mobile_node()
        elif choice == "10":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    menu()

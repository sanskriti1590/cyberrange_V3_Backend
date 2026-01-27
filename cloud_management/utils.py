import openstack
from django.conf import settings


openstack.enable_logging(debug=False)
openstack_conn = openstack.connect(cloud='openstack')

# openstack.enable_logging(debug=False)
openstack_conn = openstack.connection.from_config()
# openstack_conn = openstack.connection.Connection(auth_url=settings.AUTH_URL, project_id=settings.PROJECT_ID, user_domain_name=settings.USER_DOMAIN_NAME, password=settings.PASSWORD, username=settings.USERNAME)

def get_instance_images():
    images = openstack_conn.image.images()
    choices = [(image.id, image.name) for image in images]
    return choices

def get_instance_flavors():
    flavors = openstack_conn.compute.flavors()
    choices = [(flavor.id, flavor.name) for flavor in flavors]
    return choices

def get_image_detail(image_id):
    try:
        image = openstack_conn.image.get_image(image_id)
    except Exception as e:
        image = None
    return image

def get_flavor_detail(flavor_id):
    try:
        flavor = openstack_conn.compute.get_flavor(flavor_id)
    except Exception as e:
        flavor = None
    return flavor

def get_cloud_network(network_id):
    try:
        network = openstack_conn.network.get_network(network_id)
    except Exception as e:
        network = None
    return network

def get_cloud_subnet(subnet_id):
    try:
        subnet = openstack_conn.network.get_subnet(subnet_id)
    except Exception as e:
        subnet = None
    return subnet

def get_cloud_router(router_id):
    try:
        router = openstack_conn.network.get_router(router_id)
    except Exception as e:
        router = None
    return router

def get_cloud_instance(instance_id):
    try:
        instance = openstack_conn.get_server_by_id(instance_id)
    except Exception as e:
        instance = None
    return instance

def get_instance_private_ip(instance):
    private_ip = openstack_conn.get_server_private_ip(instance)
    return private_ip

def get_instance_public_ip(instance):
    public_ip = openstack_conn.get_server_public_ip(instance)
    return public_ip

def get_instance_console(instance):
    instance_console = openstack_conn.compute.create_server_remote_console(server=instance, protocol='vnc', type='novnc')
    return instance_console

def create_cloud_network(network_name_initial="", subnet_cidr = "192.168.169.0/24", network_name="", subnet_name=""):
    if len(network_name_initial) > 0:
        network_name = network_name_initial + "_network"
        subnet_name = network_name_initial + "_subnet"

    network = openstack_conn.network.create_network(name=network_name)
    subnet = openstack_conn.network.create_subnet(name=subnet_name, network_id=network.id, ip_version=4, cidr=subnet_cidr, dns_nameservers=['8.8.8.8','8.8.4.4'])
    return network, subnet

def create_cloud_router(router_name_initial="", router_name=""):
    if len(router_name_initial) > 0:
        router_name = router_name_initial + "_router"
    router = openstack_conn.network.create_router(name=router_name)
    return router

def connect_router_to_public_network(router, public_network_name="Public_Net"):
    public_network = openstack_conn.get_network(public_network_name)
    ex_gw_info = openstack_conn._build_external_gateway_info(public_network.id, True, None)
    print("\n\n Routersssss \n\n")
    print("\n\n", ex_gw_info, "\n\n")
    print("\n\n", router, "\n\n")
    updated_router = openstack_conn.network.update_router(router, external_gateway_info=ex_gw_info)
    return updated_router

def connect_router_to_private_network(router, private_network_subnet):
    updated_router = openstack_conn.network.add_interface_to_router(router, subnet_id=private_network_subnet.id)
    return updated_router

def create_cloud_instance(instance_name, instance_image_id, instance_flavor_id, instance_network_id, instance_availability_zone="nova"):
    if isinstance(instance_network_id, list):
        networks = [{"uuid": net_id} for net_id in instance_network_id if net_id]
    elif isinstance(instance_network_id, str):
        networks = [{"uuid": instance_network_id}]
    else:
        networks = []
    instance = openstack_conn.compute.create_server(
            name=instance_name,
            availability_zone= instance_availability_zone,
            image_id=instance_image_id,
            flavor_id=instance_flavor_id, 
            networks=networks,
        )
    instance_wait = openstack_conn.compute.wait_for_server(instance, wait=600)
    try:
        instance_info = instance_wait.to_dict()
        for address_obj in instance_info.get("addresses",{}).values():
            if address_obj :
                for single_obj in address_obj:
                    internet_protocol = single_obj.get("addr","")
    except :
        internet_protocol = ""
    return instance, internet_protocol

def delete_cloud_instance(instance):
    openstack_conn.compute.delete_server(instance.id)
    instance_wait = openstack_conn.compute.wait_for_delete(instance)
    return instance_wait

def disconnect_router_from_private_network(router_id, private_network_subnet_id):
    try:
        openstack_conn.network.remove_interface_from_router(router_id, private_network_subnet_id)
    except Exception as e:
        print(f"Subnet ID {private_network_subnet_id} is not connected with the Router ID {router_id}")

def delete_cloud_router(router_id):
    router = get_cloud_router(router_id)
    if router:
        openstack_conn.network.delete_router(router_id)

def delete_cloud_network(network_id, subnet_id):
    subnet = get_cloud_subnet(subnet_id)
    if subnet:
        openstack_conn.network.delete_subnet(subnet_id)
    
    network = get_cloud_network(network_id)
    if network:
        openstack_conn.network.delete_network(network_id)

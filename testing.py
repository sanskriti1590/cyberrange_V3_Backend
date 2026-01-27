import datetime
from collections import OrderedDict

validated_data = OrderedDict([
    ('scenario_id', 'lkdsqFk5g7kzoG5'),
    ('participant_data', [{'participant_email': 'user9@bhumi.com', 'participant_machine': 'Firewall'}]),
    ('user', {
        'user_id': 'PnKf5bllAj', 'user_full_name': 'Ankaj Gupta', 'mobile_number': 9898989898, 'email': 'ankaj@bhumiitech.com',
        'user_avatar': 'https://cyberrangebackend1.bhumiitech.com/static/images/user_avatars/avatar_10.png', 'user_role': 'WHITE TEAM', 'is_active': True,
        'is_premium': True,
        'is_verified': True, 'is_admin': True, 'is_superadmin': True, 'created_at': datetime.datetime(2024, 8, 23, 13, 1, 4, 37000),
        'updated_at': datetime.datetime(2024, 9, 27, 12, 13, 49, 334000)
    }),
    ('scenario', {
        'id': 'lkdsqFk5g7kzoG5', 'creator_id': 'PnKf5bllAj', 'name': 'Ankaj Testing 10:08',
        'category_id': 'OEnzi', 'severity': 'Very Easy',
        'description': '<p </p>',
        'objective': '<p </p>',
        'prerequisite': '<p >',
        'thumbnail_url': 'https://cyberrangebackend1.bhumiitech.com/static/images/corporate_scenario_thumbnails/lkdsqFk5g7kzoG5_thumbnail_1753936757.jpg',
        'files_data': {'red_team': [], 'blue_team': [], 'purple_team': [],
                       'yellow_team': []}, 'infra_id': 'AUQeGChNevAWv9YZK2Cf',
        'is_approved': True, 'is_prepared': True,
        'created_at': datetime.datetime(2025, 7, 31, 10, 9, 17, 166000),
        'updated_at': datetime.datetime(2025, 7, 31, 10, 13, 43, 499000),
        'flag_data': {'red_team': [], 'blue_team': ['6doUtSrgYhxGAMrF6yMDgaF9qyilOP'],
                      'purple_team': [], 'yellow_team': []}
    }),
    ('scenario_infra', {
        'id': 'AUQeGChNevAWv9YZK2Cf',
        'networks': [{'network_name': 'Network -1', 'subnet_name': 'Network -1', 'cidr_ip': '192.168.1.210/24'},
                     {'network_name': 'Network -2', 'subnet_name': 'Network -2', 'cidr_ip': '192.168.2.210/24'}],
        'routers': [{'name': 'Router-1', 'is_internet_required': True, 'network_name': ['Network -1']}],
        'instances': [
            {'name': 'Firewall', 'flavor': '3', 'network': ['Network -1', 'Network -2'], 'image': '21ea39c5-a8f2-4745-b329-93f84b9182fb', 'team': 'BLUE',
             'ip_address': '192.168.1.210'}
        ],
        'firewall': [],
        'created_at': datetime.datetime(2025, 7, 31, 10, 13, 27, 373000),
        'updated_at': datetime.datetime(2025, 7, 31, 10, 13, 27, 373000)}),
    ('participant_machine_dict', {'Firewall': 'qYy2psAaRy'})
])

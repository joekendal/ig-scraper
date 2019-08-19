import boto3, subprocess, time, atexit, logging
from botocore.exceptions import ClientError



class EC2Proxy:
    def __init__(self, id: int, log: object):
        self.id = id
        self.log = logging.getLogger(__name__)
        self.ec2 = ec2 = boto3.client('ec2')
        self.instanceID = self.__get_ec2_instance(self.id)
        self.ssh = None
        self.publicIP = self._get_ip_address()

        self.__open_ssh_tunnel(self.publicIP)
        atexit.register(self.close)

    def close(self):
        self.__close_ssh_tunnel()

    def __open_ssh_tunnel(self, ip):
        if self.ssh: self.__close_ssh_tunnel()
        self.log.info(f'Opening SSH tunnel to {ip}')
        self.ssh = subprocess.Popen([
            "ssh", "-D", str(self.id + 1080), "-CqN",
            "-i", "~/.ssh/igscraper.pem",
            "-o", "StrictHostKeyChecking=no",
            "ubuntu@{}".format(ip)
        ])
        time.sleep(3)

    def _get_ip_address(self):
        address = self.ec2.describe_addresses(Filters=[
            {'Name': 'instance-id', 'Values': [self.instanceID]}
        ])['Addresses']
        if not address:
            allocation = self.ec2.allocate_address(Domain='vpc')
            new_ip = allocation['PublicIp']
            response = self.ec2.associate_address(
                AllocationId=allocation['AllocationId'],
                InstanceId=self.instanceID
            )
            return new_ip
        else:
            return address[0]['PublicIp']

    def __close_ssh_tunnel(self):
        self.log.info("Closing SSH tunnel")
        self.ssh.terminate()

    def __get_ec2_instance(self, id):
        filters = [
            {'Name': 'tag:purpose', 'Values': ['Instagram']},
            {'Name': 'tag:id', 'Values': [str(id)]},
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped',
                                                       'stopping', 'pending']}
        ]
        req = self.ec2.describe_instances(Filters=filters)
        reservations = req['Reservations']
        if reservations:
            instances = []
            for item in reservations: instances.extend(item['Instances'])
            if (len(reservations) > 1) or (len(instances) > 1):
                pass # raise error
            else:
                # Check state
                state = instances[0]['State']['Name']
                if state == "stopped" or state == "stopping":
                    if state == "stopping":
                        time.sleep(30)
                    # Start stopped instance
                    instance = self.ec2.start_instances(InstanceIds=[instances[0]['InstanceId']])
                    instanceID = instance['StartingInstances'][0]['InstanceId']
                    return instanceID
                elif state == "running" or state == "pending":
                    instanceID = instances[0]['InstanceId']
                    return instanceID
        else:
            # Create new EC2 instance
            instance = self.ec2.run_instances(
                ImageId='ami-077a5b1762a2dde35', # Ubuntu 18
                InstanceType='t2.nano',
                KeyName='igscraper',
                MaxCount=1,
                MinCount=1,
                InstanceInitiatedShutdownBehavior='terminate',
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {
                                'Key': 'purpose',
                                'Value': 'Instagram'
                            },
                            {
                                'Key': 'id',
                                'Value': str(id)
                            }
                        ]
                    }
                ],
                NetworkInterfaces = [
                    {
                        'SubnetId': 'subnet-0a01fe9a954cd2030',
                        'DeviceIndex': 0,
                        'AssociatePublicIpAddress': True,
                        'Groups': ['sg-05bc78b497690b39e']
                    }
                ],
            )

            instanceID = instance['Instances'][0]['InstanceId']
            self.log.info("Starting new EC2 instance...")
            time.sleep(60)
            return instanceID


    def __close_ec2_instance(self):
        pass

    def change_ip_address(self):
        filters = [
            {'Name': 'instance-id', 'Values': [self.instanceID]}
        ]
        addresses = self.ec2.describe_addresses(Filters=filters)['Addresses']
        if addresses:
            for address in addresses:
                self.ec2.disassociate_address(AssociationId=address['AssociationId'])
                self.ec2.release_address(AllocationId=address['AllocationId'])

        allocation = self.ec2.allocate_address(Domain='vpc')
        new_ip = allocation['PublicIp']

        response = self.ec2.associate_address(
            AllocationId=allocation['AllocationId'],
            InstanceId=self.instanceID
        )

        self.__open_ssh_tunnel(new_ip)
        self.publicIP = new_ip

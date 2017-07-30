# AWS High Availability Scripts

[Short youtube demo video](https://youtu.be/OhtGjDPTunQ)

The script starts by quering the metadata in order to get a temporary access key and learn the virtual network interface name (eni) and route table the vMX is connected to.

The script requires some access privileges to use the API. This can be configured by assigning a IAM role (changeRoute) to the vMX instance with a policy allowing access to at least ec2:ReplaceRoute and ec2:DescribeRouteTables.
JSON formatted policy:

```
{
  "Version": "2012-10-17",
    "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:AssociateRouteTable",
      "ec2:CreateRoute",
      "ec2:CreateRouteTable",
      "ec2:DeleteRoute",
      "ec2:DeleteRouteTable",
      "ec2:DescribeRouteTables",
      "ec2:DescribeVpcs",
      "ec2:ReplaceRoute",
      "ec2:DisassociateRouteTable",
      "ec2:ReplaceRouteTableAssociation",
      "ec2:DescribeRegions"
        ],
      "Resource": "*"
    }
  ]
}
```

The scripts can be installed by uploading them onto a vMX running 16.1 or newer into /var/db/scripts/op, together with the followign Junos configuration:

```
jnpr@vmx1> file list /var/db/scripts/op/

/var/db/scripts/op/:
aws-document.py
aws-replace-route.py

jnpr@vmx1> show configuration system scripts
op {
      file aws-document.py;
      file aws-replace-route.py;
}
language python;

```

IMPORTANT: The script needs to resolve DNS names for the service API and needs a reachable
nameserver. This can be configured as follows (using Google public DNS):

```
conf
set system name-server 8.8.8.8
commit
```

Adding a static route that points to the vMX's ge-0/0/0 interface is now a simple step away:

```
jnpr@vmx1> op aws-replace-route.py interface ge-0/0/0 prefix 193.5.1.0/24

jnpr@vmx1>
```

To get a bit more verbose output, one can add a debug option:

```
jnpr@vmx1> op aws-replace-route.py interface ge-0/0/0 prefix 193.5.1.0/24 debug 1
ge-0/0/0 has mac 0a:15:a0:ce:db:2f
vpc_id=vpc-ad28dfca interface_id=eni-23c0722f region=eu-west-1
route_table_id = rtb-7090fc17
call_aws_ec2: Action=ReplaceRoute&DestinationCidrBlock=193.5.1.0%2F24&NetworkInterfaceId=eni-23c0722f&RouteTableId=rtb-7090fc17&Version=2016-09-15
response: <?xml version="1.0" encoding="UTF-8"?>
<ReplaceRouteResponse xmlns="">
  <requestId>bc084989-12cc-42a6-9d21-be75b93a8972</requestId>
  <return>true</return>
</ReplaceRouteResponse>
```

If successful, a single syslog message is generated:

```
jnpr@mw-vmx1> show log messages | match aws
May  9 13:40:48  mw-vmx1 cscript.crypto: set aws ec2 route 193.5.1.0/24 via eni-5334405f (ge-0/0/0) in rtb-7090fc17 successful
```

To verify if it actually worked, use the AWS Management Console for VPC or query the route table 
from a Linux instance with the package awscli installed:

```
ubuntu@ip-10-5-0-47:~$ aws ec2 describe-route-tables
{
  "RouteTables": [
  {
    "RouteTableId": "rtb-8746c6e0",
      "VpcId": "vpc-7851b61f",
      "Associations": [
      {
        "RouteTableId": "rtb-8746c6e0",
        "RouteTableAssociationId": "rtbassoc-c9f32daf",
        "Main": true
      }
    ],
      "PropagatingVgws": [],
      "Routes": [
      {
        "GatewayId": "local",
        "DestinationCidrBlock": "172.19.0.0/16",
        "State": "active",
        "Origin": "CreateRouteTable"
      }
    ],
      "Tags": []
  },
  {
    "RouteTableId": "rtb-3977165e",
    "VpcId": "vpc-29f90c4e",
    "Associations": [
    {
      "RouteTableId": "rtb-3977165e",
      "RouteTableAssociationId": "rtbassoc-93b300f5",
      "Main": true
    }
    ],
      "PropagatingVgws": [],
      "Routes": [
      {
        "GatewayId": "local",
        "DestinationCidrBlock": "10.150.0.0/16",
        "State": "active",
        "Origin": "CreateRouteTable"
      }
    ],
      "Tags": []
  },
  {
    "RouteTableId": "rtb-6bca370f",
    "VpcId": "vpc-a4d9d7c1",
    "Associations": [
    {
      "RouteTableId": "rtb-6bca370f",
      "RouteTableAssociationId": "rtbassoc-ab01bbcf",
      "Main": true
    }
    ],
      "PropagatingVgws": [],
      "Routes": [
      {
        "GatewayId": "local",
        "DestinationCidrBlock": "172.31.0.0/16",
        "State": "active",
        "Origin": "CreateRouteTable"
      },
      {
        "GatewayId": "igw-bd0c75d8",
        "DestinationCidrBlock": "0.0.0.0/0",
        "State": "active",
        "Origin": "CreateRoute"
      }
    ],
      "Tags": []
  },
  {
    "RouteTableId": "rtb-7090fc17",
    "VpcId": "vpc-ad28dfca",
    "Associations": [
    {
      "RouteTableId": "rtb-7090fc17",
      "RouteTableAssociationId": "rtbassoc-3c40ff5a",
      "Main": true
    }
    ],
      "PropagatingVgws": [],
      "Routes": [
      {
        "InstanceId": "i-041b5a5f965f0a9aa",
        "DestinationCidrBlock": "193.5.1.0/24",
        "NetworkInterfaceId": "eni-23c0722f",
        "InstanceOwnerId": "610418335740",
        "State": "active",
        "Origin": "CreateRoute"
      },
      {
        "GatewayId": "local",
        "DestinationCidrBlock": "10.5.0.0/16",
        "State": "active",
        "Origin": "CreateRouteTable"
      },
      {
        "GatewayId": "igw-762ab312",
        "DestinationCidrBlock": "0.0.0.0/0",
        "State": "active",
        "Origin": "CreateRoute"
      }
    ],
      "Tags": []
  }
  ]
}
ubuntu@ip-10-5-0-47:~$
```

## show route script aws-show-route.py

This script retrieves and displays any static route configured for the given interface
in Amazon VPC. It can be used to verify successful operation of aws-replace-route.py.

```
jnpr@mw-vmx1> op aws-show-route.py interface ge-0/0/0
193.5.1.0/24 via eni-5334405f (ge-0/0/0) in rtb-7090fc17
```

## Event script use with RPM

The op script can be triggered automatically via an event generated by RPM (Real-time Performance Monitoring) in Junos. Each vMX pings an interface of the other vMX and kicks the script to change the static route pointing to the local interface if the rother vMX can't be reached anymore. 
The script is also triggered once after booting up the instance to set the route. The last router coming up will remain the active router until a failover happens.

Both vMX rpm and event configurations are equal, except for the remote IP to ping:

```
services {
  rpm {
    probe icmp-ping-probe {
      test ping-probe-test {
        probe-type icmp-ping;
        target address 10.5.1.29;
        test-interval 10;
      }
    }
  }
}
```

```
event-options {
  policy aws-replace-route-policy {
    events [ ping_test_failed jtask_task_begin ];
    within 300 {
      trigger on 1;
    }
    then {
      event-script aws-replace-route.py {
        arguments {
          interface ge-0/0/0;
          prefix 193.5.1.0/24;
        }
      }
    }
  }
}
```

```
system {
  scripts {
    op {
      file aws-document.py;
      file aws-replace-route.py;
      file aws-show-route.py;
    }
    language python;
  }
}
```

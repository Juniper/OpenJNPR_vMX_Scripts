# Copyright (c) 2017, Juniper Networks, Inc.
# All rights reserved.

import sys
import datetime
import hashlib
import hmac
import urllib2
import json
import argparse
import re
import logging
import jcs
from subprocess import check_output
from lxml import etree


def call_aws_ec2(request, region, access_key, secret_key, authorization_token):

    method = 'GET'
    service = 'ec2'

    # host endpoint is different per region
    host = 'ec2.' + region + '.amazonaws.com'
    endpoint = 'https://' + host

    # Key derivation functions. See:
    # http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def getSignatureKey(key, dateStamp, regionName, serviceName):
        kDate = sign(('AWS4' + key).encode('utf-8'), dateStamp)
        kRegion = sign(kDate, regionName)
        kService = sign(kRegion, serviceName)
        kSigning = sign(kService, 'aws4_request')
        return kSigning

    # Create a date for headers and the credential string
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope

    # ************* TASK 1: CREATE A CANONICAL REQUEST *************
    # http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

    # Step 1 is to define the verb (GET, POST, etc.)--already done.
    # Step 2: Create canonical URI--the part of the URI from domain to query
    # string (use '/' if no path)
    canonical_uri = '/'

    # Step 3: Create the canonical query string. In this example (a GET request),
    # request parameters are in the query string. Query string values must
    # be URL-encoded (space=%20). The parameters must be sorted by name.
    # For this example, the query string is pre-formatted in the request
    # variable.
    canonical_querystring = request

    # Step 4: Create the canonical headers and signed headers. Header names
    # must be trimmed and lowercase, and sorted in code point order from
    # low to high. Note that there is a trailing \n.
    canonical_headers = 'host:' + host + '\n' + 'x-amz-date:' + amzdate + '\n'

    # Step 5: Create the list of signed headers. This lists the headers
    # in the canonical_headers list, delimited with ";" and in alpha order.
    # Note: The request can include any headers; canonical_headers and
    # signed_headers lists those that you want to be included in the
    # hash of the request. "Host" and "x-amz-date" are always required.
    signed_headers = 'host;x-amz-date'

    # Step 6: Create payload hash (hash of the request body content). For GET
    # requests, the payload is an empty string ("").
    payload_hash = hashlib.sha256('').hexdigest()

    # Step 7: Combine elements to create create canonical request
    canonical_request = method + '\n' + canonical_uri + '\n' + canonical_querystring + \
        '\n' + canonical_headers + '\n' + signed_headers + '\n' + payload_hash

    # ************* TASK 2: CREATE THE STRING TO SIGN*************
    # Match the algorithm to the hashing algorithm you use, either SHA-1 or
    # SHA-256 (recommended)
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = datestamp + '/' + region + \
        '/' + service + '/' + 'aws4_request'
    string_to_sign = algorithm + '\n' + amzdate + '\n' + credential_scope + \
        '\n' + hashlib.sha256(canonical_request).hexdigest()

    # ************* TASK 3: CALCULATE THE SIGNATURE *************
    # Create the signing key using the function defined above.
    signing_key = getSignatureKey(secret_key, datestamp, region, service)

    # Sign the string_to_sign using the signing_key
    signature = hmac.new(signing_key, (string_to_sign).encode(
        'utf-8'), hashlib.sha256).hexdigest()

    # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST ***********
    # The signing information can be either in a query string value or in
    # a header named Authorization. This code shows how to use a header.
    # Create authorization header and add to request headers
    authorization_header = algorithm + ' ' + 'Credential=' + access_key + '/' + \
        credential_scope + ', ' + 'SignedHeaders=' + \
        signed_headers + ', ' + 'Signature=' + signature

    # The request can include any headers, but MUST include "host", "x-amz-date",
    # and (for this scenario) "Authorization". "host" and "x-amz-date" must
    # be included in the canonical_headers and signed_headers, as noted
    # earlier. Order here is not significant.
    # Python note: The 'host' header is added automatically by the Python
    # 'requests' library.
    headers = {'x-amz-date': amzdate, 'Authorization': authorization_header,
               'X-Amz-Security-Token': authorization_token}

    # ************* SEND THE REQUEST *************
    request_url = endpoint + '?' + canonical_querystring
    logging.debug("request_url" + request_url)
    req = urllib2.Request(request_url)
    req.add_header('x-amz-date', amzdate)
    req.add_header('Authorization', authorization_header)
    req.add_header('X-Amz-Security-Token', authorization_token)
    r = urllib2.urlopen(req).read()
    # get rid of namespace for easier parsin
    r = re.sub(r"xmlns=\"[^\"]+", "xmlns=\"", r)

    return r


def main():

    usage = """
    This script shows the static route for the given interface
    via Amazon EC2 CreateRoute

    op aws-replace-route.py interface <interface> prefix <ipv4-cidr-prefix/mask> \
       [role <iam-role-name>]  [debug <level>]

    Default AWS IAM role is 'changeRoute' 

    Set debug level to 1 to get debugging information along the way
    Set debug level to 2 to also get the complete VPC routing table on the interface

  """

    parser = argparse.ArgumentParser(description='replace-route')
    parser.add_argument("-interface", help="local interface", type=str)
    parser.add_argument("-role", help="IAM role name", type=str)
    parser.add_argument("-debug", help="debug level", type=int)
    args = parser.parse_args()

    if type(args.interface) is str:
        interface = args.interface
    else:
        print usage
        exit()

    if type(args.debug) is int:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    iam_role = 'changeRoute'
    if type(args.role) is str:
        iam_role = args.role

    try:
        eths = check_output(['/sbin/ifconfig', interface])
    except:
        print "interface " + interface + " doesn't exist"
        exit()

    m = re.search('i802\s+(.+)', eths)
    if not m:
        # maybe we are running in linux
        m = re.search('HWaddr\s+([0-9:a-f]+)', eths)
    else:
        print "can't find mac address for interface " + interface
        exit()

    macaddr = m.group(1)

    # normalize address for ec2 lookup to work
    macaddr = ":".join([i.zfill(2) for i in macaddr.split(":")]).lower()

    logging.debug(interface + " has mac " + macaddr)

    cloud_init_url = "http://169.254.169.254/latest/meta-data/"
    url = cloud_init_url + "network/interfaces/macs/" + macaddr + "/interface-id"
    logging.debug("url=" + url)
    interface_id = urllib2.urlopen(url).read()

    url = cloud_init_url + "network/interfaces/macs/" + macaddr + "/vpc-id"
    vpc_id = urllib2.urlopen(url).read()

    url = cloud_init_url + "placement/availability-zone"
    region = urllib2.urlopen(url).read()
    region = region[:-1]

    logging.debug("vpc_id=" + vpc_id + " interface_id=" +
                  interface_id + " region=" + region)

    # read temporary credentials via cloud-init. Requires pre-defined IAM role
    # changeRoute
    url = cloud_init_url + "iam/security-credentials/" + iam_role
    cred = urllib2.urlopen(url).read()
    data = json.loads(cred)
    access_key = data['AccessKeyId']
    secret_key = data['SecretAccessKey']
    authorization_token = data['Token']

    if access_key is None or secret_key is None or authorization_token is None:
        print 'No AWS access key available.'
        sys.exit()

    # get VPS routing table to find the one assigned to our interface (via
    # vpc-id)
    r = call_aws_ec2('Action=DescribeRouteTables&Version=2016-11-15',
                     region, access_key, secret_key, authorization_token)
    # find routeTableId used to manage the VPC on the interface of interest
    obj = etree.fromstring(r)
    table = obj.xpath('./routeTableSet/item[vpcId="%s"]' % vpc_id)[0]
    logging.debug(etree.tostring(table))
    route_table_id = table.findtext('routeTableId')
    logging.debug("route_table_id = " + route_table_id)

    for route in table.findall('./routeSet/item'):
        route_prefix = route.findtext('destinationCidrBlock')
        route_interface = route.findtext('networkInterfaceId')
        if route_prefix and route_interface and route_interface == interface_id:
            print route_prefix + " via " + route_interface + " (" + interface + ") in " + route_table_id


if __name__ == "__main__":
    main()

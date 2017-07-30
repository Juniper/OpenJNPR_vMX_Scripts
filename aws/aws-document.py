# Copyright (c) 2017, Juniper Networks, Inc.
# All rights reserved.

import urllib2

document = urllib2.urlopen("http://169.254.169.254/latest/dynamic/instance-identity/document").read()
print(document)


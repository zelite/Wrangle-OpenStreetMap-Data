# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import difflib
import pickle
import pprint
import re
from collections import defaultdict

import lxml.etree as ET
import requests
from bs4 import BeautifulSoup

import csv_unicode

__author__ = 'jose.alves-rausch'


# General Checks

def count_tags(element, tags):
    """ Increments the tag type counter in the tags dictionary
    with the element tag name.

    :param element: XML element
    :param tags: dictionary with count of each tag type
    :return: dictionary with count of each tag type
    """
    # if keys dont exist they are created with a value 0 as default
    tags[element.tag] += 1
    return tags

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

def key_type(element, keys):
    """ Increments the key type counter in the keys dictionary
    based on the kind of key found.

    :param element: XML element
    :param keys: dictionary with count of each key type
    :return: dictionary with count of each key type
    """
    if element.tag == "tag":
        for key in element.iter():
            key_name = key.attrib["k"]
            if lower.search(key_name):
                keys["lower"] += 1
            elif lower_colon.search(key_name):
                keys["lower_colon"] += 1
            elif problemchars.search(key_name):
                keys["problemchars"] += 1
                print("Problematic key:", key_name) # if there are prob chars we want to see which they are
            else:
                keys["other"] += 1
    return keys


def get_user(element):
    """ Gets the user id (uid) from the xml element

    :param element: XML element
    :return:  user id (uid)
    """
    if element.tag in ["node", "way", "relation"]:
        return element.attrib["uid"]
    else:
        return None


# Audit validity


def iterative_validator(filename, schema):
    """ Validates the XML OSM file using the provided schema.
    Code based on code by Stephen1 in udacity forums:
    https://discussions.udacity.com/t/p3-auditing-validity/37922/7?u=josear

    :param filename: XML file path
    :param schema: schema .xsd file for validation
    :return: prints errors found
    """
    xmlschema_doc = ET.parse(schema)
    xmlschema = ET.XMLSchema(xmlschema_doc)
    for event, element in ET.iterparse(filename, events=("end", )):
        if not xmlschema.validate(element):
            print(xmlschema.error_log)

# Audit Accuracy
# On http://stadtplan.goettingen.de/
# it is possible to search the streetname of the city of goettingen.
# Could not find any other official source to check for accuracy
# DeutschePost provides data of all streetnames, postcodes and house numbers. But
# it is a paid service.


def download_street_names():
    """ Gets street names from the city of goettingen
    city map website: http://www.stadtplan.goettingen.de

    :return: list of street names
    """
    try:
        # if data is already in the pickle file, load it and return it
        with open("street_names.plk", "rb") as pkl_file:
            street_names = pickle.load(pkl_file)
    except IOError:
        # if that fails, then get the data from the goettingen city website
        r = requests.get("http://www.stadtplan.goettingen.de/start/querywin.php4",
                     params={"str": "", "alph":1})
        soup = BeautifulSoup(r.content, "lxml")
        street_names = []
        for street in soup.find_all("option"):
            street_names.append(street.attrs["value"])
        with open("street_names.plk", "wb") as output:
            pickle.dump(street_names, output)
    return street_names


def get_street_name(element):
    """ Gets street names from nodes and ways.

    :param element: XML element
    :return: street name found in the element
    """
    if element.tag == "node" or element.tag == "way":
        tags = {child.attrib["k"]: child.attrib["v"] for child in element.iter("tag")}
        if tags.has_key("addr:street"):
            # in nodes the street name is usually under the key "addr:street"
            return tags["addr:street"]
        elif element.tag == "way" and tags.has_key("highway") and tags.has_key("name"):
            # a way with the "highway" and "name" key is a street. The street name is the name value
            return tags["name"]
        else:
            return None

# Audit Uniformity

international = re.compile("^\+49 [0-9]{3,4} [ 0-9]*$") #

def phone_format(element, phone_formats):
    """ Increments the phone format type counter in the phone_formats dictionary
    based on the phone format (international format or other). If the phone number
    is other, the value of the phone number is printed.

    :param element: XML element
    :param phone_formats: dictionary with count of each phone format type
    :return: dictionary with count of each phone number type
    """
    for tag in element.iter("tag"):
        if tag.attrib["k"] in  ["phone", "fax"]:
            phone = tag.attrib["v"]
            if international.match(phone):
                phone_formats["international_format"] += 1
            else:
                phone_formats["other"] +=1
                print(phone)
    return phone_formats


# Process map with all audits

def process_map(filename):
    """ Processes the XML OSM file and returns
    information about the number of tags, keys,
    unique users, street_names and phone formats

    :param filename: XML file path
    :return: tuple with:
                tags: dictionary with count of each tag type
                keys: dictionary with count of each key type
                users: set of unique user ids
                street_names: set with street names found in dataset
                phone_formats
    """
    tags = defaultdict(int)
    keys = defaultdict(int)
    phone_formats = defaultdict(int)
    users = set()
    street_names = set()
    for _, element in ET.iterparse(filename):
        key_type(element, keys)
        count_tags(element, tags)
        uid = get_user(element)
        if uid: # if get_user returns None, we ignore it
            users.add(uid)
        street = get_street_name(element)
        if street: # if street is None, we ignore it
            street_names.add(street)
        phone_format(element, phone_formats)
    return tags, keys, users, street_names, phone_formats

if __name__ == "__main__":
    map = "goettingen.osm"
    # Audit Validity
    print("Start XML validation")
    #If there are errors, they will be printed
    iterative_validator(filename=map, schema="API_v0.6.xsd")
    print("End XML Validation - If nothing was printed, then XML file is valid acccording to the provided schema")
    # Process Map
    tags, keys, users, street_names, phones = process_map(map)
    # converting default dicts to dict for pretty printing
    print("Number of tags:")
    pprint.pprint(dict(tags))
    print("Problematic Keys: ")
    pprint.pprint(dict(keys))
    print("Users: ")
    pprint.pprint(users)
    print("Phone Formats:")
    pprint.pprint(dict(phones))
    #Audit Accuracy
    goe_street_names = download_street_names()
    with open("to_correct.csv", "wb") as f:
        print("Writing non matching street names to", f.name)
        f_writer = csv_unicode.UnicodeWriter(f)
        f_writer.writerow(["OSM", "Gottingen"])
        for street in street_names:
            closest = difflib.get_close_matches(street, goe_street_names)
            if closest:
                if not closest[0] == street: # if match is not perfect, record in csv file
                    f_writer.writerow([street, closest[0]])







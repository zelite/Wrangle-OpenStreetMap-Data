#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import codecs
import json
import re
from collections import defaultdict

import lxml.etree as ET
import phonenumbers

import csv_unicode

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
addr = re.compile(r'^addr:')
addr_too_much = re.compile(r"addr:.+:.+")
CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

def get_correct_name(old_name, corrections):
    """ Get correct name for old name

    :param old_name: street name to be corrected
    :param corrections: dictionary with correction mappings
    :return: new name
    """
    if old_name in corrections.keys():
        print("Fixing one instance of: ", old_name, " => ", corrections[old_name])
        return corrections[old_name]
    else:
        # if the name is not in the corrections dict,
        # then it does not need to be corrected.
        return old_name


def fix_street_name(element_dict, corrections):
    """ Fixes the street name of the element dictionary
    :param element_dict: dictionary with the data of a OSM XML element
    :return: element_dict with the address fixed
    """

    if element_dict["type"] == "node" or element_dict["type"] == "way":
        # does it have a street field?
        if element_dict.has_key("address") and element_dict["address"].has_key("street"):
            old_name = element_dict["address"]["street"]
            element_dict["address"]["street"] = get_correct_name(old_name, corrections)
        elif element_dict["type"] == "way" and element_dict.has_key("highway") and element_dict.has_key("name"):
            old_name = element_dict["name"]
            element_dict["name"] = get_correct_name(old_name, corrections)
    return element_dict


def streets_to_fix(filename):
    """ Gets the streetnames to correct from the
    csv file created and edited during the audit process.
    :param filename: csv file with streetnames to correct
    :return: dictionary with the mapping of the old_name: correct_name.
    """
    corrections = {}
    with open(filename) as f:
        f_reader = csv_unicode.UnicodeReader(f)
        _ = next(f_reader) # i dont need the headers
        for row in f_reader:
            if row[2] == "True":
                corrections[row[0]] = row[1]
    return corrections

def format_phone_number(number):
    """ Converts a phone number to a standard format using the
    INTERNATIONAL convention of phone number formats. Phone
    numbers are considered to be from Germany

    :param number: string with phone number
    :return: string with phone number formatted
    """
    # some numbers start with 49, without the leading "+"
    # this would be misinterpreted by the parsing function
    if number.startswith("49"):
        number = "+"+number
    # some numbers have a thin space (unicode: \u2009 ) separating the numbers
    number = number.replace(u"\u2009", " ")
    number_object = phonenumbers.parse(number,"DE") # split to remove whitespace
    return phonenumbers.format_number(number_object, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

def fix_numbers(element_dict):
    """ Corrects phone and fax numbers

    :param element_dict: dictionary with the data of a OSM XML element
    :return: dictionary with the phone anf fax numbers fixed
    """
    for key in ["phone", "fax", "contact:phone"]:
        try:
            # some entries have two phone numbers separated by comma
            number = element_dict[key]
            if number == u"keine":# some phone fields have this text
                element_dict.pop(key)
            else:
                number = [format_phone_number(n.strip()) for n in number.split(",")]
                # if only one element, then put it out of the list
                element_dict[key] = number[0] if len(number) == 1 else number
        except KeyError:
            continue
    return element_dict


def shape_element(element):
    node = defaultdict(list)  # using defaultdict to simplify pos and node_refs insertion
    if element.tag == "node" or element.tag == "way":
        created = {}
        address = {}
        for key, value in element.attrib.items():
            if key in CREATED:
                # tags in CREATED got to a sub dict
                created[key] = value
            elif key == "lat":
                node["pos"].insert(0, float(value))
            elif key == "lon":
                node["pos"].append(float(value))
            else:
                node[key] = value
        # handle the tags key value pairs
        for child in element.iter("tag"):
            tag_key = child.attrib["k"]
            tag_value = child.attrib["v"]
            if addr.search(tag_key):
                # if there is a second ":" that separates the type/direction of a street ignore it
                if addr_too_much.search(tag_key):
                    continue
                else:
                    address[tag_key[5:]] = tag_value
            else:
                node[tag_key] = tag_value
        # handle the node refs
        for child in element.iter("nd"):
            node["node_refs"].append(child.attrib["ref"])

        # finish up
        node["type"] = element.tag
        if address:
            node["address"] = address
        node["created"] = created
        return dict(node)

    else:
        return None



def process_map(file_in, pretty = False):
    # You do not need to change this file
    file_out = "{0}.json".format(file_in)
    data = []
    corrections = streets_to_fix("to_correct_edited.csv")
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                el = fix_street_name(el, corrections)
                el = fix_numbers(el)
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data


if __name__ == "__main__":
    data = process_map('goettingen.osm', True)
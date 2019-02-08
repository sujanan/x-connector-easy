#!/usr/bin/python3

import argparse
import json
import os.path
import random
import string
import xml.etree.cElementTree as ET
from xml.dom import minidom

INIT_FILENAME = "init.json"


def rmext(filename):
    e = ".json"

    if e not in filename:
        return filename

    i = filename.index(e)
    if i + len(e) != len(filename):
        return filename

    return filename[:i]


def randword(length):
    return "".join(
        random.choice(string.ascii_lowercase) for i in range(length))


def parsejson(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename) as jsonfile:
        return json.load(jsonfile)


class PropKind:
    Init = 0
    Meth = 1


class Proxy(object):
    _attribs = {
        "name": randword(10),
        "xmlns": "http://ws.apache.org/ns/synapse",
        "startOnLoad": "true",
        "statistics": "disable",
        "trace": "disable",
        "transports": "http,https"
    }

    _indention = 2

    def __init__(self, meth_name, conn_name, init, meth, attribs={}):
        self.init = init
        self.meth = meth
        self.meth_name = meth_name
        self.conn_name = conn_name

        for a in attribs:
            if a in Proxy._attribs:
                Proxy._attribs[a] = attribs[a]

        self.xml = ET.Element("proxy", Proxy._attribs)
        bodybase = ET.fromstring(self._bodybase())

        self._wrap_tag = bodybase.find("inSequence")
        self._init_tag = self._wrap_tag.find(self._init_tag_name())
        self._meth_tag = self._wrap_tag.find(self._meth_tag_name())

        for key in init:
            self.addproperty(key, PropKind.Init)
        for key in meth:
            self.addproperty(key, PropKind.Meth)

        self.xml.append(bodybase)

    def addproperty(self, key, kind):
        prop = ET.Element("property", {
            "name": key,
            "expression": "json-eval($.{})".format(key)
        })
        self._wrap_tag.insert(0, prop)
        tag = None
        if kind == PropKind.Init:
            tag = self._init_tag
        elif kind == PropKind.Meth:
            tag = self._meth_tag

        ET.SubElement(tag, key).text = "{{$ctx:{key}}}".format(key=key)

    def toprettyxml(self):
        return minidom.parseString(ET.tostring(self.xml)).toprettyxml(
            encoding="utf-8", indent=" " * Proxy._indention).decode("utf-8")

    def _init_tag_name(self):
        return "{}.init".format(self.conn_name)

    def _meth_tag_name(self):
        return "{}.{}".format(self.conn_name, self.meth_name)

    def _bodybase(self):
        return ("<target>"
                "<inSequence>"
                "<{init_tag}/>"
                "<{meth_tag}/>"
                "<respond/>"
                "</inSequence>"
                "<outSequence/>"
                "<faultSequence/>"
                "</target>".format(
                    init_tag=self._init_tag_name(),
                    meth_tag=self._meth_tag_name()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "method_name",
        type=str,
        help=("json file with required data named after the"
              "method wanted to get executed. e.g. getAllCats.json"))
    parser.add_argument(
        "-p",
        "--proxy",
        nargs=1,
        help="generates proxy xml for a given method",
        metavar="CONNECTOR")
    args = parser.parse_args()

    data_filename = args.method_name
    proxy_enabled = args.proxy

    init = parsejson(INIT_FILENAME)
    meth = parsejson(data_filename)

    if proxy_enabled:
        conn_name = proxy_enabled[0]
        meth_name = rmext(data_filename)
        p = Proxy(
            conn_name,
            meth_name,
            init=[*init],
            meth=[*meth],
            attribs={"name": "{}_{}".format(conn_name, meth_name)})
        print(p.toprettyxml())
    else:
        pass

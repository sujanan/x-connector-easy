#!/usr/bin/python3

import re
import sys
import json
import socket
import random
import string
import os.path
import argparse
import requests
import xml.etree.cElementTree as etree
from xml.dom import minidom

FILENAME_RE = (
    ".*"  # connector name with any character except newline
    "_"  # connector name and method name are seperated by '_'
    ".*"  # connector name with any character except newline
    "\.json$"  # file extension
)


def validfilename(filename):
    r = re.search(FILENAME_RE, filename)
    return True if r else False


def rmext(filename):
    e = ".json"

    if e not in filename:
        return filename

    i = filename.index(e)
    if i + len(e) != len(filename):
        return filename

    return filename[:i]


def conn_meth(name):
    conn_meth = name.split("_")
    return conn_meth[0], conn_meth[1]


def randword(length):
    return "".join(
        random.choice(string.ascii_lowercase) for i in range(length))


def parsejson(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename) as jsonfile:
        return json.load(jsonfile)


def proxyname(conn_name, meth_name):
    return "{}_{}".format(conn_name, meth_name)


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

    def __init__(self, conn_name, meth_name, init, meth, attribs={}):
        self.init = init
        self.meth = meth
        self.meth_name = meth_name
        self.conn_name = conn_name

        for a in attribs:
            if a in Proxy._attribs:
                Proxy._attribs[a] = attribs[a]

        self.xml = etree.Element("proxy", Proxy._attribs)
        bodybase = etree.fromstring(self._bodybase())

        self._wrap_tag = bodybase.find("inSequence")
        self._init_tag = self._wrap_tag.find(self._init_tag_name())
        self._meth_tag = self._wrap_tag.find(self._meth_tag_name())

        for key in init:
            self.addproperty(key, PropKind.Init)
        for key in meth:
            self.addproperty(key, PropKind.Meth)

        self.xml.append(bodybase)

    def addproperty(self, key, kind):
        prop = etree.Element("property", {
            "name": key,
            "expression": "json-eval($.{})".format(key)
        })
        self._wrap_tag.insert(0, prop)
        tag = None
        if kind == PropKind.Init:
            tag = self._init_tag
        elif kind == PropKind.Meth:
            tag = self._meth_tag

        etree.SubElement(tag, key).text = "{{$ctx:{key}}}".format(key=key)

    def toprettyxml(self):
        return minidom.parseString(etree.tostring(self.xml)).toprettyxml(
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


def post(url, payload, verbose):
    res = requests.post(url, json=payload)

    code = res.status_code

    code_msg = requests.status_codes._codes[code][0]
    code_msg = code_msg.split("_")
    code_msg = [msg.title() for msg in code_msg]
    code_msg = " ".join(code_msg)

    headers = res.headers if res.headers else {}
    headers = [
        "{key}: {value}".format(key=key, value=headers[key]) for key in headers
    ]
    headers = "\n".join(headers)

    content = res.content.decode("utf-8")

    return ("HTTP/1.1 {code} {code_msg}\n"
            "{headers}\n\n"
            "{content}\n".format(
                code=code, code_msg=code_msg, headers=headers,
                content=content))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "connector_method",
        type=str,
        help=(
            "json file with required data named accoding to format "
            "$connectorname_$methodname.json e.g. catconnector_getAllCats.json"
        ))
    parser.add_argument(
        "-p",
        "--proxy",
        action="store_true",
        help="generates proxy xml for a given method")
    args = parser.parse_args()

    proxy_enabled = args.proxy

    data_fullpath = args.connector_method

    data_filename = os.path.basename(data_fullpath)

    if not validfilename(data_filename):
        sys.exit()

    conn_name, meth_name = conn_meth(rmext(data_filename))

    init_path = os.path.join(
        os.path.dirname(data_fullpath), "{}_init.json".format(conn_name))
    meth_path = data_fullpath
    init = parsejson(init_path)
    meth = parsejson(meth_path)

    if proxy_enabled:
        p = Proxy(
            conn_name,
            meth_name,
            init=[*init],
            meth=[*meth],
            attribs={"name": proxyname(conn_name, meth_name)})
        print(p.toprettyxml())
    else:
        url = "http://{hostname}:8280/services/{proxyname}".format(
            hostname=socket.gethostname(),
            proxyname=proxyname(conn_name, meth_name))
        resstr = post(url, payload={**init, **meth}, verbose=True)
        print(resstr)

from setuptools import setup
from re import findall

with open("debian/changelog", "r") as clog:
    _, version, _ = findall(
        r"(?P<src>.*) \((?P<version>.*)\) (?P<suite>.*); .*",
        clog.readline().strip(),
    )[0]

setup(
    name="bluering",
    version=version,
    description="Tool to communicate with some health sensor rings",
    url="http://www.average.org/bluering/",
    author="Eugene Crosser",
    author_email="crosser@average.org",
    install_requires=["bleak"],
    license="MIT",
    packages=[
        "bluering",
    ],
    scripts=["scripts/bluering"],
    long_description=open("README.md").read(),
)

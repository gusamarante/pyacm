from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = '1.0'
DESCRIPTION = 'ACM Term Premium'

# Setting up
setup(
    name="pyacm",
    version=VERSION,
    author="Tobias Adrian, Richard K. Crump, Emanuel Moench",
    maintainer="Gustavo Amarante",
    maintainer_email="developer@dsgepy.com",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    packages=find_packages(),
    install_requires=[
        'matplotlib',
        'numpy',
        'pandas',
        'scikit-learn',
        'statsmodels',
    ],
    keywords=[
        'asset pricing',
        'yield curve',
        'term premium',
    ],
)

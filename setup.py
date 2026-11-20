from setuptools import setup, find_packages

setup(name='vcst',
      version="0.0.11",
      description="VUnit & cocotb smashed Together",
      author="James Price",
      author_email="jpwice100@gmail.com",
      packages=find_packages(),
      python_requires=">=3.9",
      install_requires=["vunit-hdl>=4.7.1,<6", "cocotb>=1.8,<2"]
     )

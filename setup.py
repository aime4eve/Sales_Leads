from setuptools import setup, find_packages

setup(
    name="hkt_agent_framework",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        # 其他依赖项可以从requirements.txt中读取
    ],
    author="伍志勇",
    author_email="",  # 可选
    description="HKT Agent Framework for Sales Leads",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.6",
) 
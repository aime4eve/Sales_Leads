from setuptools import setup, find_packages

setup(
    name="sales_leads",
    version="1.0.0",
    packages=find_packages(),
    py_modules=[
        'sync_hktlora',
        'hktloraweb',
        'LeadsInsight',
        'log_checker',
        'log_cleaner'
    ],
    install_requires=[
        'playwright',
    ],
    python_requires='>=3.7',
) 
from setuptools import setup, find_packages

setup(
    name="ai-hedge-fund",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit==1.32.0",
        "pandas==1.3.5",
        "numpy==1.21.6",
        "plotly==5.13.1",
        "matplotlib==3.5.3",
        "python-dotenv==1.0.0",
        "requests==2.28.2",
        "google-generativeai==0.3.2",
        "tabulate==0.9.0",
        "colorama==0.4.6",
        "rich==13.3.5",
        "pygments==2.14.0",
        "mdurl==0.1.2",
        "markdown-it-py==2.2.0",
    ],
    python_requires=">=3.9,<3.10",
) 
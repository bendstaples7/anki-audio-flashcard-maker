"""
Setup configuration for Cantonese Anki Generator.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cantonese-anki-generator",
    version="0.1.0",
    author="Cantonese Anki Generator Team",
    description="Automated flashcard creation from Google Docs and audio files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "librosa>=0.9.0",
        "webrtcvad>=2.0.10",
        "google-auth>=2.0.0",
        "google-auth-oauthlib>=0.5.0",
        "google-auth-httplib2>=0.1.0",
        "google-api-python-client>=2.0.0",
        "genanki>=0.13.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "hypothesis>=6.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },
)
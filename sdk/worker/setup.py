"""
OpenClaw Worker SDK 包配置
"""

from pathlib import Path

from setuptools import find_packages, setup

# Resolve README.md relative to project root
readme_path = Path(__file__).parent.parent.parent / "README.md"
with open(readme_path, "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="openclaw-worker-sdk",
    version="0.2.0",
    author="OpenClaw Team",
    author_email="team@openclaw.dev",
    description="OpenClaw Multi-Agent Framework - Worker SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/openclaw/openclaw",
    packages=find_packages(where="."),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "aiohttp>=3.8.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "openclaw-worker=worker.runtime:main",
        ],
    },
    package_data={
        "worker": ["py.typed"],
    },
)
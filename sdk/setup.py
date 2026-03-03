from setuptools import setup, find_packages

setup(
    name="promptcode",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
    ],
    python_requires=">=3.11",
    description="PromptCode SDK — tracked LLM calls for challenge submissions",
)

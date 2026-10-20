import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "rag-server")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "backend")))


def pytest_configure(config):
    # registers the "live" marker so you don't get the warning (no pytest.ini needed)
    config.addinivalue_line("markers", "live: needs running servers")
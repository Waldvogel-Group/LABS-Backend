from backend.setup.setup import Setup
from twisted.internet import reactor
from yaml import load, SafeLoader

if __name__ == "__main__":
    with open("config.yml", "r") as file:
        config = load(file, SafeLoader)

    flowmachine = Setup(config)
    reactor.run()

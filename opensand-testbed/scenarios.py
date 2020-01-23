from abc import ABC, abstractmethod
from loguru import logger
import docker
import time

class Scenario(ABC):
    def __init__(self, name, testbed, benchmarks):
        self.name = name
        self.testbed = testbed
        self.benchmarks = benchmarks

    @abstractmethod
    def deploy_scenario(self):
        self.testbed.start_testbed()
        self.testbed.connect_terminal_workstation()

    def run_benchmarks(self, deployed=False):
        for benchmark in self.benchmarks:
            if not deployed:
                self.deploy_scenario()
            benchmark.run()

    def print_results(self):
        print("*"*25)
        print("Benchmark Results for ", self.name)
        print("*"*25)
        for benchmark in self.benchmarks:
            print("****", benchmark.name, "****")
            benchmark.print_results()

class PlainScenario(Scenario):
    def deploy_scenario(self, testbed_up=False):
        super().deploy_scenario()

class OpenVPNScenario(Scenario):
    def deploy_scenario(self, testbed_up=False):
        super().deploy_scenario()
        docker_client = docker.from_env()
        terminal_workstation = docker_client.containers.get("ws-st")
        # Satellite latency means that it takes OpenVPN a long time to establish the connection, waiting is easiest
        logger.debug("Launching OVPN and waiting...")
        terminal_workstation.exec_run("openvpn --config /root/client.ovpn --daemon")
        time.sleep(20)

class QPEPScenario(Scenario):
    def deploy_scenario(self, testbed_up=False):
        super().deploy_scenario()
        docker_client = docker.from_env()

        logger.debug("Configuring Client Side of QPEP Proxy")
        terminal_container = docker_client.containers.get("terminal")
        terminal_container.exec_run("bash /opensand_config/configure_qpep.sh")

        logger.debug("Configuring Gateway Side of QPEP Proxy")
        gateway_workstation = docker_client.containers.get("ws-gw")
        gateway_workstation.exec_run("bash /opensand_config/configure_qpep.sh")

        logger.debug("Launching QPEP Client")
        terminal_container.exec_run("go run /root/go/src/qpep/main.go -client -gateway 172.22.0.9", detach=True)
        logger.debug("Launching QPEP Gateway")
        gateway_workstation.exec_run("go run /root/go/src/qpep/main.go", detach=True)
        logger.success("QPEP Running")

class QPEPAckScenario(Scenario):
    def deploy_scenario(self, testbed_up=False, ack_level=4):
        if not testbed_up:
            super().deploy_scenario()

        docker_client = docker.from_env()
        terminal_container = docker_client.containers.get("terminal")
        gateway_workstation = docker_client.containers.get("ws-gw")
        if testbed_up:
            logger.debug("Killing any prior QPEP")
            terminal_container.exec_run("pkill -9 main")
            gateway_workstation.exec_run("pkill -9 main")
            time.sleep(1)
        else:
            logger.debug("Configuring Client Side of QPEP Proxy")
            terminal_container.exec_run("bash /opensand_config/configure_qpep.sh")

            logger.debug("Configuring Gateway Side of QPEP Proxy")
            gateway_workstation.exec_run("bash /opensand_config/configure_qpep.sh")

        logger.debug("Launching QPEP Client")
        terminal_container.exec_run("go run /root/go/src/qpep/main.go -client -gateway 172.22.0.9 -decimate " + str(ack_level), detach=True)
        logger.debug("Launching QPEP Gateway")
        gateway_workstation.exec_run("go run /root/go/src/qpep/main.go -decimate " + str(ack_level), detach=True)
        logger.success("QPEP Running")


class QPEPCongestionScenario(Scenario):
    def deploy_scenario(self, testbed_up=False, congestion_window=10):
        if not testbed_up:
            super().deploy_scenario()

        docker_client = docker.from_env()
        terminal_container = docker_client.containers.get("terminal")
        gateway_workstation = docker_client.containers.get("ws-gw")
        if testbed_up:
            logger.debug("Killing any prior QPEP")
            terminal_container.exec_run("pkill -9 main")
            gateway_workstation.exec_run("pkill -9 main")
            time.sleep(1)
        else:
            logger.debug("Configuring Client Side of QPEP Proxy")
            terminal_container.exec_run("bash /opensand_config/configure_qpep.sh")

            logger.debug("Configuring Gateway Side of QPEP Proxy")
            gateway_workstation.exec_run("bash /opensand_config/configure_qpep.sh")

        logger.debug("Launching QPEP Client")
        terminal_container.exec_run("go run /root/go/src/qpep/main.go -client -gateway 172.22.0.9 -congestion " + str(congestion_window), detach=True)
        logger.debug("Launching QPEP Gateway")
        gateway_workstation.exec_run("go run /root/go/src/qpep/main.go -congestion " + str(congestion_window), detach=True)
        logger.success("QPEP Running")


class PEPsalScenario(Scenario):
    def __init__(self, name, testbed, benchmarks, terminal=True, gateway=False):
        self.terminal  = terminal
        self.gateway = gateway
        super().__init__(name=name, testbed=testbed, benchmarks=benchmarks)

    def deploy_scenario(self, testbed_up=False):
        if not testbed_up:
            super().deploy_scenario()
        logger.debug("Starting PEPsal Scenario")
        docker_client = docker.from_env()

        if self.terminal and self.gateway:
            logger.debug("Deploying PEPsal in Distributed Mode")

        if self.terminal:
            logger.debug("Deploying PEPsal on Terminal Endpoint")
            terminal_client = docker_client.containers.get("terminal")
            terminal_client.exec_run("bash /opensand_config/launch_pepsal.sh")
        if self.gateway:
            logger.debug("Deploying PEPsal on Gateway Endpoint")
            gateway_client = docker_client.containers.get("gateway")
            gateway_client.exec_run("bash /opensand_config/launch_pepsal.sh")
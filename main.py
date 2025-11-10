import argparse
import asyncio
import logging
import os
import sys

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential
from kmd_nexus_client import NexusClientManager
from odk_tools.tracking import Tracker
from proces.config import load_excel_sheet

nexus: NexusClientManager
tracker: Tracker

medicin: list[str] = None

proces_navn = "Markering af Risikosituationslægemidler i Nexus"

async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from populate workqueue!")


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
 
            try:
                # Process the item here
                pass
            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":

    ats = AutomationServer.from_environment() 
    workqueue = ats.workqueue()

    parser = argparse.ArgumentParser(description=proces_navn)
    parser.add_argument(
        "--excel-file", 
        default="./Indholdsstoffer.xlsx", 
        help="Populate the workqueue instead of processing it"
        )
    args = parser.parse_args()

    # Validate Excel file exists
    if not os.path.isfile(args.excel_file):
        raise FileNotFoundError(f"Excel file not found: {args.excel_file}")
    
    medicin = load_excel_sheet(args.excel_file)

    # Initialize external systems for automation here..
    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    nexus = NexusClientManager(
        nexus_credential.data["instance"],
        nexus_credential.username,
        nexus_credential.password,
    )

    tracker = Tracker(
        username=tracking_credential.username,
        password=tracking_credential.password
    )

    # Queue management
    if args.queue:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))

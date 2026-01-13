import argparse
import asyncio
import logging
import os
import sys

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential
from kmd_nexus_client import NexusClientManager
from kmd_nexus_client.tree_helpers import filter_by_path
from odk_tools.tracking import Tracker
from odk_tools.reporting import report
from proces.config import load_excel_sheet
from proces.nexus_service import NexusService

nexus: NexusClientManager
tracker: Tracker

risikolægemidler: list[str]

proces_navn = "Markering af Risikosituationslægemidler i Nexus"


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Indlæser kø")
    organisation = nexus.organisationer.hent_organisation_ved_navn("Sundhedsklinik VIVO")
    
    if organisation is None:
        raise ValueError("Org ikke fundet")

    borgere = nexus.organisationer.hent_borgere_for_organisation(organisation)

    for borger in borgere:
        kø_item = {
            "cpr": borger["patientIdentifier"]["identifier"]
        }
        workqueue.add_item(kø_item, kø_item["cpr"])


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
            
            try:
                borger = nexus.borgere.hent_borger(data["cpr"])
                if borger is None:
                    raise ValueError("Borger ikke fundet")
                medicinkort = nexus.medicin.hent_medicinkort(borger)
                
                # Skip inactive medication cards
                if not medicinkort["active"]:
                    logger.info(f"Borger har ikke et aktivt medicinkort")
                    continue #Skip og gå til næste item
                    
                mediciner = nexus.medicin.filtrer_medicin(medicinkort)

                rapport:bool = False

                for medicin in mediciner:
                    lægemiddel = medicin["drug"]["activeIngredient"]
                    bemærkning = str(medicin["remarks"]) if medicin["remarks"] is not None else ""

                    er_risikomiddel = False
                    har_risiko_tekst = False

                    if lægemiddel in risikolægemidler:
                        er_risikomiddel = True
                    
                    if "RISIKOSITUATIONSLÆGEMIDDEL".lower() in bemærkning.lower():
                        har_risiko_tekst = True

                    # Switch case der til håndtering af forskellige kombinationer af har teskt og er risikomiddel
                    match (er_risikomiddel, har_risiko_tekst):
                        case (True, False):
                            # Risk medication but no risk marker - add it
                            logger.info(f"Risikokægemiddel fundet: {lægemiddel} på borger")
                            nexus_service.tilføj_risikomarkering
                            nexus_service.opret_opgave_på_indsats(borger)

                            rapport = True

                        case (False, True):
                            # Ikke risikomiddel længere
                            logger.info(f"Lægemiddel: {lægemiddel} er ikke længere risikomiddel")
                            nexus_service.fjern_risikomarkering

                            rapport = True

                        case (True, True):
                            # Har tekst og er risikomiddel
                            logger.info(f"Risikokægemiddel {lægemiddel} har allerede korrekt markering")
                        
                        case (False, False):
                            # Har ikke tekst og er ikke risikomiddel
                            logger.info(f"Lægemiddel {lægemiddel} er ikke risiko og har ingen markering")
                        
                        case _:
                            # Default case - should never be reached with boolean values, but good for safety
                            logger.warning(f"Unexpected combination: er_risikomiddel={er_risikomiddel}, har_risiko_tekst={har_risiko_tekst}")
                
                if rapport:
                    report(
                        "markering_af_risikosituationslægemidler_i_nexus",
                        "Opdateret",
                        json={
                            "Cpr": data["cpr"],
                            "Beskrivelse": "Bemærkning opdateret på en eller flere lægemidler"
                        }
                    )

                    tracker.track_task(process_name=proces_navn)
                else:
                    tracker.track_partial_task(process_name=proces_navn)

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
    
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Populate the queue with test data and exit",
    )
    args = parser.parse_args()

    # Validate Excel file exists
    if not os.path.isfile(args.excel_file):
        raise FileNotFoundError(f"Excel file not found: {args.excel_file}")
    
    risikolægemidler = load_excel_sheet(args.excel_file)

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

    nexus_service = NexusService(nexus_client=nexus)

    # Queue management
    if args.queue:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))

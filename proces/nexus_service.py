from kmd_nexus_client import NexusClientManager
from kmd_nexus_client.tree_helpers import filter_by_path
from logging import Logger, getLogger
from datetime import date


class NexusService:
    def __init__(self, nexus_client: NexusClientManager):
        self.nexus = nexus_client
        self.logger = getLogger(__name__)
    
    def opret_opgave_på_indsats(self, borger: dict):

        pathway = self.nexus.borgere.hent_visning(borger)

        if pathway is None:
            raise ValueError("P")
                
        indsats_referencer = self.nexus.borgere.hent_referencer(pathway)

        indsats_referencer = filter_by_path(
            indsats_referencer,
            "/Sundhedsfagligt grundforløb/FSIII/Indsatser/*",
            active_pathways_only=True
        )

        indsatser = self.nexus.indsatser.filtrer_indsats_referencer(indsats_referencer, True)


        indsats = next((i for i in indsatser if i.get('name') == "Medicindispensering"), None)

        if indsats is None:
            self.logger.info("Indsats ikke fundet på borger")
            raise ValueError("Indsats ikke fundet")
        
        self.logger.info("Opretter opgave")
        self.nexus.opgaver.opret_opgave(
            indsats,
            "Tværfagligt samarbejde",
            "Titel",
            "Ansvars org",
            date.today(),
            None,
            "Beskrivelse her",
        )
    
    def tilføj_risikomarkering(self, medicin: dict):
        
        self.logger.info("Tilføjer risikolægemiddel til bemærking")
        medicin["remarks"] = "RISIKOSITUATIONSLÆGEMIDDEL - " + medicin["remarks"]
        self.nexus.medicin.opdater_medicin(medicin)

    def fjern_risikomarkering(self, medicin: dict):
        

        self.logger.info("Fjerner risikolægemiddel fra bemærkning")
        bemærkning:str = medicin["remarks"]

        bemærkning = bemærkning.replace("RISIKOSITUATIONSLÆGEMIDDEL - ", "")
        bemærkning = bemærkning.replace("RISIKOSITUATIONSLÆGEMIDDEL", "")
        
        medicin["remarks"] = bemærkning
        self.nexus.medicin.opdater_medicin(medicin)
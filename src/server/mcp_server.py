#!/usr/bin/env python3
"""
Haupt-MCP-Server für Apache Solr-Dokumentensuche.

Diese Implementierung stellt MCP-Ressourcen und -Tools für die Solr-Integration bereit,
optimiert für die Verwendung mit dem MCP-Protokoll durch LLMs.
"""
import os
import json
import sys
import logging
import traceback
from typing import Dict, List, Optional, Any
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Projektpfad zum System-Pfad hinzufügen, um absolute Imports zu ermöglichen
# Dadurch können wir den Server mit 'mcp dev' und 'python run_server.py' ausführen
project_dir = str(Path(__file__).parents[2])  # Zwei Ebenen nach oben: src/server -> src -> Projektwurzel
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
    print(f"Added {project_dir} to system path")

# Importiere lokale Module
from src.server.models import SearchParams, GetDocumentParams
from src.server.solr_client import SolrClient

# Logger für diese Datei konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-server")

# Umgebungsvariablen laden
load_dotenv()

# MCP-Server-Konfiguration
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Solr Search")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8765"))

# Solr-Verbindungskonfiguration
SOLR_BASE_URL = os.getenv("SOLR_BASE_URL", "http://localhost:8983/solr")
SOLR_COLLECTION = os.getenv("SOLR_COLLECTION", "documents")
SOLR_USERNAME = os.getenv("SOLR_USERNAME", "")
SOLR_PASSWORD = os.getenv("SOLR_PASSWORD", "")


# MCP-Server ohne Lifespan-Kontext erstellen (für MCP 1.6.0 Kompatibilität)
app = FastMCP(MCP_SERVER_NAME)

# Solr-Client als globale Variable initialisieren (für MCP 1.6.0 Kompatibilität)
solr_client = SolrClient(
    base_url=SOLR_BASE_URL,
    collection=SOLR_COLLECTION,
    username=SOLR_USERNAME,
    password=SOLR_PASSWORD
)


@app.resource("solr://search/{query}")
async def search_solr(query: str):
    """
    Einfache Ressource für die Suche in Solr-Dokumenten.
    
    Diese Ressource bietet eine einfache Schnittstelle für Solr-Suchen
    über den MCP-Protokoll-Ressourcenmechanismus.
    
    Args:
        query (str): Die Suchanfrage
        
    Returns:
        str: JSON-String mit Suchergebnissen
    """
    try:
        logger.info(f"Verarbeite Suchanfrage mit Query: {query}")
        results = await solr_client.search(query)
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.error(f"Fehler in search_solr-Ressource: {e}")
        logger.error(traceback.format_exc())
        return json.dumps({"error": f"Fehler bei der Verarbeitung der Suche: {str(e)}"}, indent=2)


@app.tool()
async def search(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool für erweiterte Dokumentensuche.
    
    Dieses Tool bietet eine erweiterte Suchfunktionalität mit Filtern,
    Sortierung und Paginierung für Solr-Dokumente.
    
    Args:
        params (Dict[str, Any]): Suchparameter, einschließlich query, filter_query, sort, rows, start
        
    Returns:
        Dict[str, Any]: Suchergebnisse oder Fehlermeldung
    """
    try:
        logger.info(f"Verarbeite search-Tool-Anfrage mit Parametern: {params}")
        search_params = SearchParams(**params)
        
        results = await solr_client.search(
            query=search_params.query,
            filter_query=search_params.filter_query,
            sort=search_params.sort,
            rows=search_params.rows,
            start=search_params.start
        )
        
        return results
    except Exception as e:
        logger.error(f"Fehler im search-Tool: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"Fehler bei der Verarbeitung der Suche: {str(e)}"}


@app.tool()
async def get_document(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool zum Abrufen spezifischer Dokumente.
    
    Dieses Tool ermöglicht das Abrufen von Dokumenten nach ID mit optionaler
    Feldauswahl.
    
    Args:
        params (Dict[str, Any]): Parameter mit id und optionalem fields-Array
        
    Returns:
        Dict[str, Any]: Das abgerufene Dokument oder Fehlermeldung
    """
    try:
        logger.info(f"Verarbeite get_document-Tool-Anfrage mit Parametern: {params}")
        document_params = GetDocumentParams(**params)
        
        document = await solr_client.get_document(
            doc_id=document_params.id,
            fields=document_params.fields
        )
        
        return document
    except Exception as e:
        logger.error(f"Fehler im get_document-Tool: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"Fehler beim Abrufen des Dokuments: {str(e)}"}


async def test_solr_connection():
    """
    Testet die Verbindung zum Solr-Server vor dem Start des MCP-Servers.
    
    Returns:
        bool: True, wenn die Verbindung erfolgreich war, sonst False
    """
    try:
        logger.info("Teste Solr-Verbindung...")
        async with httpx.AsyncClient() as client:
            ping_url = f"{SOLR_BASE_URL}/{SOLR_COLLECTION}/admin/ping"
            response = await client.get(ping_url)
            response.raise_for_status()
            logger.info("Solr-Verbindung erfolgreich")
        return True
    except Exception as e:
        logger.warning(f"Solr-Verbindungstest fehlgeschlagen: {e}")
        logger.warning("Server wird gestartet, aber Solr-Suchen könnten fehlschlagen")
        return False


if __name__ == "__main__":
    # Umgebungsvariablen für den MCP-Server setzen
    os.environ["MCP_PORT"] = str(MCP_SERVER_PORT)
    
    import asyncio
    
    # Teste die Solr-Verbindung vor dem Start
    asyncio.run(test_solr_connection())
    
    try:
        # Server starten (nutzt MCP FastMCP.run() ohne Parameter für MCP 1.6.0 Kompatibilität)
        logger.info(f"Starte MCP-Server '{MCP_SERVER_NAME}' auf Port {MCP_SERVER_PORT}...")
        print(f"MCP-Server wird gestartet, nutze 'mcp dev {__file__}' für die Entwicklungsumgebung")
        print("Server ist als MCP-Protokoll verfügbar, aber nicht direkt über HTTP erreichbar")
        print("Für direkten HTTP-Zugriff bitte src/server/http_server.py verwenden")
        app.run()
    except Exception as e:
        logger.error(f"Fehler beim Starten des Servers: {e}")
        logger.error(traceback.format_exc())
# Neo4j (Docker) + ETL

This folder contains everything required to run a local Neo4j instance in Docker and load the public-transport dataset into a Neo4j knowledge graph using a Cypher ETL script.

## Contents

- `docker-compose.yaml` – starts Neo4j with the required volume mounts (data, logs, plugins, import)
- `ETL.cypher` – ETL script that reads CSVs from the Neo4j import folder and builds the graph model

## Prerequisites

- Docker Desktop (or Docker Engine) running
- The dataset CSV files downloaded (see below)

## 0) Download the CSV data (pick one city code)

Download three archives from Zenodo (record `15839004`) and select the **same city code** in each archive (e.g., `GM0047`):

- `travel_times.zip` → extract `GM0047.csv`
- `dwell_times.zip` → extract `GM0047.csv`
- `trajectories.zip` → extract `GM0047.csv`

You will end up with three CSV files (one per family) for the same city code.

## 1) Create folders and place the CSVs

From the repository root:

```bash
cd Neo4j
mkdir -p data logs plugins import/travel_times import/dwell_times import/trajectories
```

Copy/rename the CSVs into the following paths (example for `GM0059`):

- `Neo4j/import/travel_times/travel_time_GM0059.csv`
- `Neo4j/import/dwell_times/dwell_time_GM0059.csv`
- `Neo4j/import/trajectories/trajectories_GM0059.csv`

**Important:** The file names must match the pattern used inside `ETL.cypher`:

- `travel_time_<CITY>.csv`
- `dwell_time_<CITY>.csv`
- `trajectories_<CITY>.csv`

## 2) Copy the ETL script into the Neo4j import folder

Neo4j can only read files from its `import/` directory. Copy the script there:

```bash
cp ETL.cypher import/ETL.cypher
```

*(Windows PowerShell: `Copy-Item ETL.cypher import\ETL.cypher`)*

## 3) Start Neo4j

```bash
docker compose up -d
```

After startup, Neo4j is typically available at:
- Browser: `http://localhost:7474`
- Bolt: `neo4j://localhost:7687`

(Exact ports depend on `docker-compose.yaml`.)

## 4) Run the ETL (load CSVs into the graph)

Run the ETL inside the container with `cypher-shell`.



```bash
docker exec neo4j cypher-shell -u neo4j -p password -d neo4j -f import/ETL.cypher
```

> Note: Replace `password` / database name with the values configured in your `docker-compose.yaml`.

### CITY parameter
If your `ETL.cypher` uses `:param CITY => 'GM0059';`, make sure it matches the CSV filenames you copied into `import/`.

## 5) Quick tests

```bash
docker exec neo4j cypher-shell -u neo4j -p password -d neo4j "MATCH (s:Stop) RETURN count(s) AS stops;"
docker exec neo4j cypher-shell -u neo4j -p password -d neo4j "MATCH (r:Route) RETURN count(r) AS routes;"
```

## What the ETL does 

- Builds core entities such as `Stop` and `Route`.
- Creates directed `LINK` edges between stops with rolling travel-time statistics and distance.
- Adds dwell-time rolling statistics on `Stop`.
- Aggregates trajectory counts and a `last_seen` timestamp on `Route`.


## Knowledge Graph (KG) schema
![KG schema diagram](docs/diagrams/KG_Schema_simple.png)

### KG schema diagram 
![KG schema diagram](docs/diagrams/KG_Schema.png)

## ETL flow diagram 

![ETL flow diagram](docs/diagrams/etl_flow.png)


## Tips

- Do **not** commit large CSVs into git. Keep them local under `Neo4j/import/`.
- If ETL becomes slow, reduce `BATCH_SIZE` or check that APOC is enabled and available.

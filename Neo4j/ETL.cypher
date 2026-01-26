////////////////////////////////////////////////////////////////////////
// 0. Constraints & Indexe
////////////////////////////////////////////////////////////////////////

CREATE CONSTRAINT stop_id_unique IF NOT EXISTS
FOR (s:Stop)
REQUIRE s.stop_id IS UNIQUE;

CREATE CONSTRAINT route_id_unique IF NOT EXISTS
FOR (r:Route)
REQUIRE r.route_id IS UNIQUE;

CREATE CONSTRAINT trip_unique IF NOT EXISTS
FOR (t:Trip)
REQUIRE (t.trip_id, t.date) IS UNIQUE;

CREATE CONSTRAINT segment_id_unique IF NOT EXISTS
FOR (seg:TravelSegment)
REQUIRE seg.segment_id IS UNIQUE;

// Indexe
CREATE INDEX route_line IF NOT EXISTS
FOR (r:Route)
ON (r.line);

CREATE INDEX trip_route IF NOT EXISTS
FOR (t:Trip)
ON (t.route_id);

CREATE INDEX segment_from_to IF NOT EXISTS
FOR (seg:TravelSegment)
ON (seg.from_stop_id, seg.to_stop_id);

////////////////////////////////////////////////////////////////////////
// 1. Travel Times laden – NUR Januar 2022
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
   LOAD CSV WITH HEADERS
   FROM 'file:///travel_times/travel_time_GM0047.csv' AS row
   FIELDTERMINATOR ','
   WITH row
   WHERE row.date IS NOT NULL AND row.date <> ''
   RETURN row
  ",
  "
   // 1) Datum parsen & auf Januar 2022 filtern
   WITH row, date(row.date) AS serviceDate
   WHERE serviceDate >= date('2022-01-01')
     AND serviceDate <  date('2024-01-01')

   // 2) Zeiten parsen (Format: 2022-01-01 12:55:23+0000 -> 2022-01-01T12:55:23)
   WITH row, serviceDate,
        datetime(replace(left(row.from_time, 19), ' ', 'T')) AS fromTime,
        datetime(replace(left(row.to_time,   19), ' ', 'T')) AS toTime

   // 3) Reisedauer in Sekunden
   WITH row, serviceDate, fromTime, toTime,
        duration.inSeconds(fromTime, toTime).seconds AS rawTravelSecs
   WITH row, serviceDate, fromTime, toTime,
        CASE WHEN rawTravelSecs >= 0 THEN rawTravelSecs ELSE 0 END AS travel_time_seconds

   // 4) Aliase für Felder
   WITH row, serviceDate, fromTime, toTime, travel_time_seconds,
        row.lau           AS lau,
        row.line          AS line,
        toString(row.route) AS route_id,
        row.trip          AS trip_id,
        row.from_stop     AS from_stop_id,
        row.to_stop       AS to_stop_id,
        row.from_geometry AS from_geom,
        row.to_geometry   AS to_geom

   // 5) Stops
   MERGE (from:Stop {stop_id: from_stop_id})
     ON CREATE SET
       from.lau          = lau,
       from.geometry_wkt = from_geom

   MERGE (to:Stop {stop_id: to_stop_id})
     ON CREATE SET
       to.lau            = lau,
       to.geometry_wkt   = to_geom

   // 6) Route
   MERGE (r:Route {route_id: route_id})
     ON CREATE SET
       r.line = line,
       r.lau  = lau

   // 7) Trip (Trip_id + date!)
   MERGE (t:Trip {trip_id: trip_id, date: toString(serviceDate)})
     ON CREATE SET
       t.line     = line,
       t.route_id = route_id,
       t.lau      = lau

   MERGE (r)-[:HAS_TRIP]->(t)

   // 8) TravelSegment: EIN globales Segment pro Stop-Paar
   WITH r, t, from, to, serviceDate, fromTime, toTime,
        travel_time_seconds, lau, from_stop_id, to_stop_id
   WITH r, t, from, to, serviceDate, fromTime, toTime,
        travel_time_seconds, lau, from_stop_id, to_stop_id,
        from_stop_id + '|' + to_stop_id AS segment_id

   MERGE (seg:TravelSegment {segment_id: segment_id})
     ON CREATE SET
       seg.from_stop_id = from_stop_id,
       seg.to_stop_id   = to_stop_id,
       seg.lau          = lau

   // 9) Segment-Topologie
   MERGE (from)<-[:FROM_STOP]-(seg)
   MERGE (seg)-[:TO_STOP]->(to)

   // 10) Route-zu-Segment Kante
   MERGE (r)-[:HAS_SEGMENT]->(seg)

   // 11) TRAVELS_ON Event Trip -> Segment
   MERGE (t)-[trav:TRAVELS_ON {
      date:         toString(serviceDate),
      from_time:    fromTime,
      to_time:      toTime,
      from_stop_id: from_stop_id,
      to_stop_id:   to_stop_id
   }]->(seg)
   ON CREATE SET
      trav.travel_time_seconds = travel_time_seconds
  ",
  {batchSize:10000, parallel:false}
);

////////////////////////////////////////////////////////////////////////
// 1b. Trip-Attribute berechnen (from_time, to_time, travel_time_seconds)
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
    MATCH (t:Trip)-[e:TRAVELS_ON]->(:TravelSegment)
    RETURN t, collect(e) AS evts
  ",
  "
    WITH t, evts
    UNWIND evts AS e
    WITH t,
         collect(e.travel_time_seconds) AS times,
         min(e.from_time) AS first_departure,
         max(e.to_time)   AS last_arrival
    WITH t, times, first_departure, last_arrival,
         reduce(total = 0.0, x IN times | total + coalesce(x,0)) AS total
    SET t.travel_time_seconds = total,
        t.from_time           = first_departure,
        t.to_time             = last_arrival
  ",
  {batchSize:1000, parallel:false}
);

////////////////////////////////////////////////////////////////////////
// 2. Dwell Times laden – NUR Januar 2022
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
   LOAD CSV WITH HEADERS
   FROM 'file:///dwell_times/dwell_time_GM0047.csv' AS row
   FIELDTERMINATOR ','
   WITH row
   WHERE row.date IS NOT NULL AND row.date <> ''
   RETURN row
  ",
  "
   // 1) Datum parsen & auf Januar 2022 filtern
   WITH row, date(row.date) AS serviceDate
   WHERE serviceDate >= date('2022-01-01')
     AND serviceDate <  date('2024-01-01')

   // 2) Zeiten parsen
   WITH row, serviceDate,
        datetime(replace(left(row.from_time, 19), ' ', 'T')) AS fromTime,
        datetime(replace(left(row.to_time,   19), ' ', 'T')) AS toTime

   // 3) Dwell-Dauer
   WITH row, serviceDate, fromTime, toTime,
        duration.inSeconds(fromTime, toTime).seconds AS rawDwellSecs
   WITH row, serviceDate, fromTime, toTime,
        CASE WHEN rawDwellSecs >= 0 THEN rawDwellSecs ELSE 0 END AS dwell_time_seconds

   // 4) Aliase
   WITH row, serviceDate, fromTime, toTime, dwell_time_seconds,
        row.lau           AS lau,
        row.line          AS line,
        toString(row.route) AS route_id,
        row.trip          AS trip_id,
        row.stop          AS stop_id,
        row.geometry      AS geom

   // 5) Stop, Route, Trip
   MERGE (s:Stop {stop_id: stop_id})
     ON CREATE SET
       s.lau          = lau,
       s.geometry_wkt = geom

   MERGE (r:Route {route_id: route_id})
     ON CREATE SET
       r.line = line,
       r.lau  = lau

   MERGE (t:Trip {trip_id: trip_id, date: toString(serviceDate)})
     ON CREATE SET
       t.line     = line,
       t.route_id = route_id,
       t.lau      = lau

   MERGE (r)-[:HAS_TRIP]->(t)

   // 6) DWELL_AT Event
   MERGE (t)-[dw:DWELL_AT {
      date:      toString(serviceDate),
      from_time: fromTime,
      to_time:   toTime,
      stop_id:   stop_id
   }]->(s)
   ON CREATE SET
      dw.dwell_time_seconds = dwell_time_seconds
  ",
  {batchSize:10000, parallel:false}
);

////////////////////////////////////////////////////////////////////////
// 3. Aggregat SERVES (Route -> Stop) aus DWELL_AT
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
    MATCH (r:Route)-[:HAS_TRIP]->(t:Trip)-[d:DWELL_AT]->(s:Stop)
    RETURN r, s, collect(d) AS dwells
  ",
  "
    WITH r, s, dwells
    UNWIND dwells AS d
    WITH r, s,
         collect(d.dwell_time_seconds) AS times
    WITH r, s,
         size(times) AS cnt,
         reduce(total = 0.0, x IN times | total + coalesce(x,0)) AS total
    MERGE (r)-[srv:SERVES]->(s)
    SET srv.dwell_sample_count         = cnt,
        srv.total_dwell_time_seconds   = total,
        srv.mean_dwell_time_seconds    = CASE WHEN cnt > 0 THEN total / cnt ELSE 0 END
  ",
  {batchSize:1000, parallel:false}
);

////////////////////////////////////////////////////////////////////////
// 4. Aggregat HAS_SEGMENT (Route -> TravelSegment) aus TRAVELS_ON
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
    MATCH (r:Route)-[rel:HAS_SEGMENT]->(seg:TravelSegment)<-[e:TRAVELS_ON]-(:Trip)
    RETURN r, seg, rel, collect(e) AS evts
  ",
  "
    WITH r, seg, rel, evts
    UNWIND evts AS e
    WITH r, seg, rel,
         collect(e.travel_time_seconds) AS times
    WITH r, seg, rel,
         size(times) AS cnt,
         reduce(total = 0.0, x IN times | total + coalesce(x,0)) AS total
    SET rel.segment_travel_sample_count       = cnt,
        rel.segment_total_travel_time_seconds = total,
        rel.segment_mean_travel_time_seconds  = CASE WHEN cnt > 0 THEN total / cnt ELSE 0 END
  ",
  {batchSize:1000, parallel:false}
);

////////////////////////////////////////////////////////////////////////
// 5. Aggregat auf Route: mittlere Trip-Reisezeit
////////////////////////////////////////////////////////////////////////

CALL apoc.periodic.iterate(
  "
    MATCH (r:Route)-[:HAS_TRIP]->(t:Trip)
    WHERE t.travel_time_seconds IS NOT NULL
    RETURN r, collect(t.travel_time_seconds) AS times
  ",
  "
    WITH r, times,
         size(times) AS cnt,
         reduce(total = 0.0, x IN times | total + coalesce(x,0)) AS total
    SET r.trip_sample_count              = cnt,
        r.total_trip_travel_time_seconds = total,
        r.mean_trip_travel_time_seconds  = CASE WHEN cnt > 0 THEN total / cnt ELSE 0 END
  ",
  {batchSize:1000, parallel:false}
);

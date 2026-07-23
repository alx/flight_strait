(function () {
  var data = JSON.parse(document.getElementById("flight-data").textContent);
  var refs = window.MAP_CONFIG;

  var map = L.map("map").setView([refs.reference.lat, refs.reference.lon], 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  L.marker([refs.reference.lat, refs.reference.lon]).addTo(map).bindPopup(refs.reference.label);

  if (refs.query) {
    L.circle([refs.query.lat, refs.query.lon], {
      radius: refs.query.radiusNm * 1852,
    }).addTo(map);
  }

  // Initial compass bearing (0-360) from point 1 to point 2.
  function bearing(lat1, lon1, lat2, lon2) {
    var toRad = function (d) { return (d * Math.PI) / 180; };
    var phi1 = toRad(lat1), phi2 = toRad(lat2), dLambda = toRad(lon2 - lon1);
    var y = Math.sin(dLambda) * Math.cos(phi2);
    var x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
    return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  }

  // Smallest angle (0-180) between two compass bearings.
  function angleDiff(a, b) {
    var diff = Math.abs(a - b) % 360;
    return diff > 180 ? 360 - diff : diff;
  }

  // Only keep flights heading toward or away from the corridor reference
  // point (e.g. Baku) -- excludes north/south traffic that merely clips
  // the query radius.
  function inCorridor(flight) {
    if (!refs.corridor || flight.track.length < 2) return false;
    var first = flight.track[0], last = flight.track[flight.track.length - 1];
    var flightBearing = bearing(first.lat, first.lon, last.lat, last.lon);
    var corridorBearing = bearing(refs.reference.lat, refs.reference.lon, refs.corridor.lat, refs.corridor.lon);
    var diff = angleDiff(flightBearing, corridorBearing);
    var diffReciprocal = angleDiff(flightBearing, (corridorBearing + 180) % 360);
    return Math.min(diff, diffReciprocal) <= refs.corridor.toleranceDeg;
  }

  var colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0"];

  (data.flights || []).filter(inCorridor).forEach(function (flight, i) {
    var points = flight.track.map(function (p) {
      return [p.lat, p.lon];
    });
    L.polyline(points, { color: colors[i % colors.length] })
      .addTo(map)
      .bindPopup(flight.flight || flight.hex);
  });
})();

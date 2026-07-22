(function () {
  var data = JSON.parse(document.getElementById("flight-data").textContent);
  var refs = window.CASPIAN_REFERENCE_POINTS;

  var map = L.map("map").setView([refs.baku[0], (refs.baku[1] + refs.turkmenbashi[1]) / 2], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  L.marker(refs.baku).addTo(map).bindPopup("Baku");
  L.marker(refs.turkmenbashi).addTo(map).bindPopup("Turkmenbashi");

  if (refs.query) {
    L.circle([refs.query.lat, refs.query.lon], {
      radius: refs.query.radiusNm * 1852,
    }).addTo(map);
  }

  var colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0"];

  (data.flights || []).forEach(function (flight, i) {
    var points = flight.track.map(function (p) {
      return [p.lat, p.lon];
    });
    L.polyline(points, { color: colors[i % colors.length] })
      .addTo(map)
      .bindPopup(flight.flight || flight.hex);
  });
})();

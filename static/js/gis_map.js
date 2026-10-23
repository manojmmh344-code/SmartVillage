document.addEventListener("DOMContentLoaded", () => {
  const parse = (id) => {
    const element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : [];
  };
  const villages = parse("village-map-data");
  const facilities = parse("facility-map-data");
  const detailUrl = parse("map-url-template");
  const mapElement = document.getElementById("village-map");
  const listElement = document.getElementById("village-list");
  const searchInput = document.getElementById("map-search");
  const villageSelect = document.getElementById("village-filter");
  const districtSelect = document.getElementById("district-filter");
  const infrastructureSelect = document.getElementById("infrastructure-filter");
  const projectSelect = document.getElementById("project-status-filter");
  const resultCount = document.getElementById("map-result-count");
  const mapError = document.getElementById("map-error");
  const mapLoading = document.getElementById("map-loading");
  const layerToggles = [...document.querySelectorAll(".facility-layer-toggle")];
  const facilityTypes = layerToggles.map((input) => input.value);
  const enabledTypes = () => new Set(layerToggles.filter((input) => input.checked).map((input) => input.value));
  const hasVerifiedPoint = (item) =>
    item.coordinates_verified === 1 && Number.isFinite(Number(item.latitude)) &&
    Number.isFinite(Number(item.longitude)) && item.latitude !== null && item.longitude !== null;
  const projectCount = (village, status) => {
    if (status === "Planned") return village.planned_projects;
    if (status === "In Progress") return village.in_progress_projects;
    if (status === "Completed") return village.completed_projects;
    return village.project_count;
  };
  const matchesInfrastructure = (village, filter) => {
    if (filter === "water-limited") return village.water_availability < 70;
    if (filter === "road-needs-work") return village.road_status === "Needs improvement";
    if (filter === "has-schools") return village.schools > 0;
    if (filter === "has-healthcare") return village.healthcare_centers > 0;
    return true;
  };
  const villageMatches = (village) => {
    const query = searchInput.value.trim().toLocaleLowerCase();
    const selectedId = villageSelect.value;
    return (!query || village.name.toLocaleLowerCase().includes(query)) &&
      (!selectedId || String(village.id) === selectedId) &&
      (!districtSelect.value || village.district === districtSelect.value) &&
      matchesInfrastructure(village, infrastructureSelect.value) &&
      (!projectSelect.value || projectCount(village, projectSelect.value) > 0);
  };
  const escapeText = (value) => String(value ?? "");
  const detailHref = (villageId) => detailUrl.replace(/\/0$/, `/${villageId}`);
  const createText = (tag, text, className) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = escapeText(text);
    return element;
  };
  const villagePopup = (village) => {
    const content = createText("div", "", "map-popup");
    content.append(createText("h3", village.name));
    content.append(createText("p", `${village.district} District`));
    content.append(createText("p", `Population: ${Number(village.population).toLocaleString()}`));
    content.append(createText("p", `Schools: ${village.schools} · Healthcare centers: ${village.healthcare_centers}`));
    content.append(createText("p", `Drinking water availability: ${village.water_availability}%`));
    const link = createText("a", "View village details");
    link.href = detailHref(village.id);
    content.append(link);
    return content;
  };
  const facilityPopup = (facility) => {
    const content = createText("div", "", "map-popup");
    content.append(createText("h3", facility.facility_name));
    content.append(createText("p", facility.facility_type));
    content.append(createText("p", `Village: ${facility.village_name}`));
    if (facility.address) content.append(createText("p", facility.address));
    if (facility.description) content.append(createText("p", facility.description));
    const link = createText("a", "View village details");
    link.href = detailHref(facility.village_id);
    content.append(link);
    return content;
  };

  let map = null;
  const villageMarkers = new Map();
  const facilityLayers = new Map();
  if (window.L) {
    map = L.map(mapElement, { scrollWheelZoom: true }).setView([20, 0], 2);
    const tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    }).addTo(map);
    tileLayer.on("tileload", () => { mapLoading.hidden = true; });
    tileLayer.on("tileerror", () => {
      mapError.hidden = false;
      mapLoading.hidden = true;
    });
    villages.filter(hasVerifiedPoint).forEach((village) => {
      const marker = L.circleMarker([village.latitude, village.longitude], {
        radius: 8, color: "#fff", weight: 2, fillColor: "#28764f", fillOpacity: .95,
      }).bindPopup(villagePopup(village)).bindTooltip(createText("span", village.name), { direction: "top" });
      villageMarkers.set(String(village.id), marker);
    });
    facilityTypes.forEach((type) => {
      const layer = L.layerGroup();
      facilityLayers.set(type, layer);
    });
  } else if (mapError) {
    mapError.hidden = false;
    mapLoading.hidden = true;
  }

  const makeVillageCard = (village, villageFacilities) => {
    const card = createText("article", "", "map-list-card");
    card.append(createText("h3", village.name));
    card.append(createText("p", `${village.district} District · Population ${Number(village.population).toLocaleString()}`));
    card.append(createText("p", `${village.schools} schools · ${village.healthcare_centers} healthcare centers · Water ${village.water_availability}%`));
    card.append(createText("p", `Road status: ${village.road_status} · Projects: ${village.project_count}`));
    if (hasVerifiedPoint(village)) {
      card.append(createText("p", "Verified village coordinates are mapped."));
    } else {
      card.append(createText("p", "No verified coordinates; this village is not placed on the map.", "map-location-label"));
    }
    villageFacilities.forEach((facility) => {
      const label = `${facility.facility_name} · ${facility.facility_type}${hasVerifiedPoint(facility) ? "" : " · not mapped"}`;
      card.append(createText("p", label, "map-facility"));
    });
    const link = createText("a", "View full village details", "map-village-link");
    link.href = detailHref(village.id);
    card.append(link);
    card.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      villageSelect.value = String(village.id);
      searchInput.value = village.name;
      render();
      const marker = villageMarkers.get(String(village.id));
      if (marker && map) {
        map.setView(marker.getLatLng(), 13);
        marker.openPopup();
      }
    });
    return card;
  };

  const render = () => {
    const visibleVillages = villages.filter(villageMatches);
    const visibleIds = new Set(visibleVillages.map((village) => String(village.id)));
    const visibleFacilities = facilities.filter((facility) =>
      visibleIds.has(String(facility.village_id)) &&
      enabledTypes().has(facility.facility_type) &&
      (!projectSelect.value || projectCount(villages.find((village) => village.id === facility.village_id), projectSelect.value) > 0)
    );
    listElement.replaceChildren();
    visibleVillages.forEach((village) => {
      const villageFacilities = visibleFacilities.filter((facility) => facility.village_id === village.id);
      listElement.append(makeVillageCard(village, villageFacilities));
    });
    if (!visibleVillages.length) {
      listElement.append(createText("p", "No villages match these filters.", "empty-state"));
    }
    if (resultCount) {
      const mappedVillageCount = visibleVillages.filter(hasVerifiedPoint).length;
      const mappedFacilityCount = visibleFacilities.filter(hasVerifiedPoint).length;
      resultCount.textContent = `${visibleVillages.length} village(s); ${mappedVillageCount} mapped and ${mappedFacilityCount} mapped facility marker(s).`;
    }
    if (map) {
      const visibleVillageIds = new Set(visibleVillages.map((village) => String(village.id)));
      villageMarkers.forEach((marker, villageId) => {
        if (visibleVillageIds.has(villageId)) {
          if (!map.hasLayer(marker)) marker.addTo(map);
        } else if (map.hasLayer(marker)) {
          map.removeLayer(marker);
        }
      });
      facilityLayers.forEach((layer, type) => {
        if (enabledTypes().has(type)) {
          layer.clearLayers();
          visibleFacilities.filter((facility) =>
            facility.facility_type === type && hasVerifiedPoint(facility)
          ).forEach((facility) => {
            const index = facilityTypes.indexOf(type) + 1;
            const icon = L.divIcon({
              className: "",
              html: `<span class="facility-marker facility-marker-${index}" aria-hidden="true"></span>`,
              iconSize: [24, 24],
              iconAnchor: [12, 22],
            });
            L.marker([facility.latitude, facility.longitude], { icon })
              .bindPopup(facilityPopup(facility))
              .bindTooltip(createText("span", facility.facility_name), { direction: "top" })
              .addTo(layer);
          });
          if (!map.hasLayer(layer)) layer.addTo(map);
        } else if (map.hasLayer(layer)) {
          map.removeLayer(layer);
        }
      });
    }
  };

  [searchInput, villageSelect, districtSelect, infrastructureSelect, projectSelect].forEach((control) => {
    control.addEventListener("input", render);
    control.addEventListener("change", render);
  });
  layerToggles.forEach((toggle) => toggle.addEventListener("change", render));
  villageSelect.addEventListener("change", () => {
    const marker = villageMarkers.get(villageSelect.value);
    if (marker && map) {
      map.setView(marker.getLatLng(), 13);
      marker.openPopup();
    }
  });
  if (villageSelect.value) {
    const selected = villages.find((village) => String(village.id) === villageSelect.value);
    if (selected) {
      searchInput.value = selected.name;
      const marker = villageMarkers.get(String(selected.id));
      if (marker && map) {
        map.setView(marker.getLatLng(), 13);
        marker.openPopup();
      }
    }
  }
  render();
  if (map) window.setTimeout(() => map.invalidateSize(), 100);
});

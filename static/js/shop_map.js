/*
 * DEEPLOG：ダイビングショップの地図
 *
 * 地図は Leaflet + OpenStreetMap（無料・API キー不要）。
 *   - 表示用：data-shop-map を付けた要素に、ショップの場所の地図を出す（一覧のカード・詳細画面）
 *   - 入力用：data-shop-picker を付けた要素で、地図からショップを検索して選ぶ（投稿・編集フォーム）
 *
 * 検索に使う無料の API と、守るべきルール
 *   - Nominatim（名前・住所で検索 / 地図の地点から住所を調べる）：1 秒に 1 回まで。入力のたびに検索しない（ボタンか Enter で検索）
 *   - Overpass API（地図の範囲にあるダイビングショップを探す）：広すぎる範囲は検索しない
 *   - 地図には OpenStreetMap の出典表示（attribution）を必ず出す
 */
(function () {
  "use strict";

  if (typeof L === "undefined") return;  // Leaflet が読み込めなかったときは何もしない（地図なしでもフォームは使える）

  var TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
  var NOMINATIM = "https://nominatim.openstreetmap.org";
  var OVERPASS = "https://overpass-api.de/api/interpreter";
  var JAPAN = [36.2, 138.0];       // 場所が未登録のときの中心（日本全体）
  var AREA_MIN_ZOOM = 10;          // 「この範囲のショップ」はこれ以上拡大しているときだけ検索する

  // OpenStreetMap のサーバーは、どのサイトからのアクセスか（Referer）が分からないリクエストを 403 で拒否する。
  // Django は標準で「Referrer-Policy: same-origin」（他のサイトには Referer を送らない）を返すので、
  // OpenStreetMap へのリクエストだけ、サイトのオリジン（例: https://deeplog-app.onrender.com）を送るようにする。
  // ページの URL のパスやクエリ（?mine=1 など）は送らない。
  var REFERRER_POLICY = "strict-origin-when-cross-origin";

  function tileLayer() {
    return L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION, referrerPolicy: REFERRER_POLICY });
  }

  // 選んだショップの印（画像を使わない丸い印なので、アイコン画像の読み込みに失敗しない）
  function shopPin(latlng) {
    return L.circleMarker(latlng, {
      radius: 9, color: "#04141a", weight: 2, fillColor: "#2fe0c4", fillOpacity: 1,
    });
  }

  // 検索候補の印（選ぶ前）
  function candidatePin(latlng) {
    return L.circleMarker(latlng, {
      radius: 7, color: "#2fe0c4", weight: 2, fillColor: "#0c222e", fillOpacity: 0.9,
    });
  }

  /* ------------------------------------------------------------------
   * 表示用の地図（一覧のカード・詳細画面）
   *   <div data-shop-map data-lat="26.2" data-lng="127.3" data-zoom="14" data-interactive="true"></div>
   * 一覧では 9 枚の地図を一度に作ると重いので、画面に入ったときに作る
   * ------------------------------------------------------------------ */
  function createPreview(el) {
    var lat = parseFloat(el.dataset.lat);
    var lng = parseFloat(el.dataset.lng);
    if (isNaN(lat) || isNaN(lng)) return;
    var interactive = el.dataset.interactive === "true";
    var map = L.map(el, {
      center: [lat, lng],
      zoom: parseInt(el.dataset.zoom, 10) || 14,
      zoomControl: interactive,
      dragging: interactive,
      touchZoom: interactive,
      doubleClickZoom: interactive,
      scrollWheelZoom: false,  // ページのスクロール中に地図が拡大しないように
      boxZoom: false,
      keyboard: interactive,
    });
    map.attributionControl.setPrefix(false);
    tileLayer().addTo(map);
    shopPin([lat, lng]).addTo(map);
  }

  function initPreviews() {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-shop-map]"));
    if (!els.length) return;
    if (!("IntersectionObserver" in window)) {
      els.forEach(createPreview);
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          createPreview(entry.target);
        }
      });
    }, { rootMargin: "200px" });
    els.forEach(function (el) { observer.observe(el); });
  }

  /* ------------------------------------------------------------------
   * Nominatim へのリクエストを 1 秒に 1 回までにする（利用規約）
   * ------------------------------------------------------------------ */
  var lastNominatim = 0;
  function nominatim(path, params) {
    var wait = Math.max(0, lastNominatim + 1100 - Date.now());
    lastNominatim = Date.now() + wait;
    params["format"] = "jsonv2";
    params["accept-language"] = "ja";
    var url = NOMINATIM + path + "?" + new URLSearchParams(params).toString();
    return new Promise(function (resolve) { setTimeout(resolve, wait); })
      .then(function () { return fetch(url, { referrerPolicy: REFERRER_POLICY }); })
      .then(function (res) {
        if (!res.ok) throw new Error("nominatim " + res.status);
        return res.json();
      });
  }

  // OpenStreetMap の住所タグ（addr:*）から、日本式の住所の文字列を作る
  function addressFromTags(tags) {
    if (tags["addr:full"]) return tags["addr:full"];
    var keys = ["addr:province", "addr:city", "addr:suburb", "addr:quarter",
                "addr:neighbourhood", "addr:block_number", "addr:housenumber"];
    return keys.map(function (k) { return tags[k] || ""; }).join("");
  }

  // Nominatim の display_name（「名前, 番地, 町, 市, 県, 郵便番号, 日本」の順）を、日本式の並びの住所にする
  function addressFromDisplayName(displayName, name) {
    var parts = String(displayName || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (name && parts[0] === name) parts.shift();
    parts = parts.filter(function (p) { return p !== "日本" && !/^\d{3}-?\d{4}$/.test(p); });
    return parts.reverse().join(" ");
  }

  /* ------------------------------------------------------------------
   * 入力用の地図（投稿・編集フォーム）
   * ------------------------------------------------------------------ */
  function initPicker(root) {
    var mapEl = root.querySelector("[data-picker-map]");
    var queryIn = root.querySelector("[data-shop-query]");
    var searchBtn = root.querySelector("[data-shop-search]");
    var areaBtn = root.querySelector("[data-shop-area]");
    var results = root.querySelector("[data-shop-results]");
    var status = root.querySelector("[data-shop-status]");
    var selectedBox = root.querySelector("[data-shop-selected]");
    var addressText = root.querySelector("[data-shop-address-text]");
    var clearBtn = root.querySelector("[data-shop-clear]");
    var nameIn = document.getElementById(root.dataset.nameId);
    var addressIn = document.getElementById(root.dataset.addressId);
    var latIn = document.getElementById(root.dataset.latId);
    var lngIn = document.getElementById(root.dataset.lngId);
    if (!mapEl || !nameIn || !addressIn || !latIn || !lngIn) return;

    var hasLocation = latIn.value !== "" && lngIn.value !== "";
    var start = hasLocation ? [parseFloat(latIn.value), parseFloat(lngIn.value)] : JAPAN;
    var map = L.map(mapEl, { scrollWheelZoom: false }).setView(start, hasLocation ? 15 : 5);
    map.attributionControl.setPrefix(false);
    tileLayer().addTo(map);

    var candidates = L.layerGroup().addTo(map);
    var selectedPin = null;

    function setStatus(text, isError) {
      status.textContent = text || "";
      status.classList.toggle("is-error", !!isError);
    }

    function showSelected() {
      var has = latIn.value !== "" && lngIn.value !== "";
      // 場所を選んだとき、または名前だけ入っているとき（以前に手入力した場合など）に表示する
      selectedBox.hidden = !(has || nameIn.value);
      addressText.textContent = has ? (addressIn.value || "（住所を取得できませんでした）") : "（地図の場所は未指定）";
      if (selectedPin) { map.removeLayer(selectedPin); selectedPin = null; }
      if (has) {
        selectedPin = shopPin([parseFloat(latIn.value), parseFloat(lngIn.value)]).addTo(map);
        selectedPin.bindTooltip(nameIn.value || "選んだ場所");
      }
    }

    // 地図の地点から住所（と、分かれば名前）を調べる
    function lookupAddress(lat, lng, fillName) {
      return nominatim("/reverse", { lat: lat, lon: lng, zoom: "18" })
        .then(function (data) {
          if (data && !data.error) {
            addressIn.value = addressFromDisplayName(data.display_name, data.name);
            if (fillName && !nameIn.value && data.name) nameIn.value = data.name;
          }
        })
        .catch(function () { /* 住所が取れなくても、場所は選べているので続ける */ })
        .then(showSelected);
    }

    // 候補（または地図でクリックした地点）を選ぶ
    function choose(place) {
      latIn.value = place.lat.toFixed(6);
      lngIn.value = place.lng.toFixed(6);
      if (place.name) nameIn.value = place.name;
      addressIn.value = place.address || "";
      map.setView([place.lat, place.lng], Math.max(map.getZoom(), 15));
      showSelected();
      if (!place.address) lookupAddress(place.lat, place.lng, !place.name);
      setStatus(place.name ? "「" + place.name + "」を選びました。名前は下の欄で直せます。" : "地図で指定した場所を選びました。ショップ名を入力してください。");
      if (!nameIn.value) nameIn.focus();
    }

    function showCandidates(list, emptyMessage) {
      candidates.clearLayers();
      results.innerHTML = "";
      if (!list.length) {
        results.hidden = true;
        setStatus(emptyMessage);
        return;
      }
      var bounds = [];
      list.forEach(function (place) {
        var li = document.createElement("li");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "shop-result";
        var title = document.createElement("strong");
        title.textContent = place.name || "（名前なし）";  // textContent なので、名前に HTML が入っていても安全
        var sub = document.createElement("span");
        sub.textContent = place.address || "";
        btn.appendChild(title);
        btn.appendChild(sub);
        btn.addEventListener("click", function () {
          choose(place);
          results.hidden = true;
          candidates.clearLayers();
        });
        li.appendChild(btn);
        results.appendChild(li);

        var marker = candidatePin([place.lat, place.lng]).addTo(candidates);
        marker.bindTooltip(place.name || "（名前なし）");
        marker.on("click", function () {
          choose(place);
          results.hidden = true;
          candidates.clearLayers();
        });
        bounds.push([place.lat, place.lng]);
      });
      results.hidden = false;
      if (bounds.length === 1) map.setView(bounds[0], 15);
      else map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
      setStatus(list.length + " 件見つかりました。一覧か地図の印を選んでください。");
    }

    // ① 名前・地名で検索（Nominatim）
    function searchByText() {
      var q = queryIn.value.trim();
      if (!q) {
        setStatus("ショップ名や地名を入力してください。", true);
        queryIn.focus();
        return;
      }
      searchBtn.disabled = true;
      setStatus("検索しています…");
      nominatim("/search", { q: q, limit: "8" })
        .then(function (data) {
          showCandidates((data || []).map(function (r) {
            var name = r.name || String(r.display_name || "").split(",")[0];
            return {
              name: name,
              address: addressFromDisplayName(r.display_name, name),
              lat: parseFloat(r.lat),
              lng: parseFloat(r.lon),
            };
          }), "見つかりませんでした。別の言葉で検索するか、地図をクリックして場所を指定してください。");
        })
        .catch(function () { setStatus("検索に失敗しました。時間をおいて試してください。", true); })
        .then(function () { searchBtn.disabled = false; });
    }

    // ② 地図に表示している範囲のダイビングショップを探す（Overpass API）
    function searchInArea() {
      if (map.getZoom() < AREA_MIN_ZOOM) {
        setStatus("範囲が広すぎます。探したい地域まで地図を拡大してから押してください。", true);
        return;
      }
      var b = map.getBounds();
      var bbox = [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map(function (v) { return v.toFixed(5); }).join(",");
      var query =
        "[out:json][timeout:25];(" +
        'nwr["shop"="scuba_diving"](' + bbox + ");" +
        'nwr["amenity"="dive_centre"](' + bbox + ");" +
        'nwr["sport"="scuba_diving"]["name"](' + bbox + ");" +
        ");out center 50;";
      areaBtn.disabled = true;
      setStatus("この範囲のダイビングショップを探しています…（無料の検索サーバーが混んでいると 1 分ほどかかります）");
      // 混雑で返事が来ないときに待ち続けないよう、70 秒で打ち切る
      var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      var timer = controller ? setTimeout(function () { controller.abort(); }, 70000) : null;
      fetch(OVERPASS, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "data=" + encodeURIComponent(query),
        signal: controller ? controller.signal : undefined,
        referrerPolicy: REFERRER_POLICY,
      })
        .then(function (res) {
          if (!res.ok) throw new Error("overpass " + res.status);
          return res.json();
        })
        .then(function (data) {
          // サーバー側で時間切れになったときは、200 でも remark に理由が入る
          if (data.remark && /timed out|runtime error/i.test(data.remark)) throw new Error("overpass timeout");
          return data;
        })
        .then(function (data) {
          var seen = {};
          var list = [];
          (data.elements || []).forEach(function (el) {
            var tags = el.tags || {};
            var lat = el.lat != null ? el.lat : el.center && el.center.lat;
            var lng = el.lon != null ? el.lon : el.center && el.center.lon;
            var name = tags["name:ja"] || tags.name || "";
            if (lat == null || lng == null || !name || seen[name]) return;
            seen[name] = true;
            list.push({ name: name, address: addressFromTags(tags), lat: lat, lng: lng });
          });
          showCandidates(list, "この範囲では見つかりませんでした。地図を動かして試すか、名前で検索してください。");
        })
        .catch(function () {
          setStatus("検索サーバーが混んでいて探せませんでした。少し待って試すか、名前で検索してください。", true);
        })
        .then(function () {
          if (timer) clearTimeout(timer);
          areaBtn.disabled = false;
        });
    }

    // ③ 地図をクリックして場所を指定する（候補にショップがないとき用）
    map.on("click", function (e) {
      choose({ name: "", address: "", lat: e.latlng.lat, lng: e.latlng.lng });
    });

    searchBtn.addEventListener("click", searchByText);
    areaBtn.addEventListener("click", searchInArea);
    // 検索欄で Enter を押したとき、フォームを送信せずに検索する
    queryIn.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        searchByText();
      }
    });
    clearBtn.addEventListener("click", function () {
      nameIn.value = "";
      addressIn.value = "";
      latIn.value = "";
      lngIn.value = "";
      showSelected();
      setStatus("ショップの選択を外しました。");
      queryIn.focus();
    });
    nameIn.addEventListener("input", function () {
      if (selectedPin) selectedPin.setTooltipContent(nameIn.value || "選んだ場所");
    });

    showSelected();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initPreviews();
    document.querySelectorAll("[data-shop-picker]").forEach(initPicker);
  });
})();

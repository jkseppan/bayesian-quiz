function renderDistChart(svgId, estimates, unit, answer) {
    var svg = document.getElementById(svgId);
    if (!svg || estimates.length === 0) return;

    var W = 800, H = 320;
    var pad = {top: 20, right: 40, bottom: 50, left: 40};
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;

    function bell(x, mu, sigma) {
        var z = (x - mu) / sigma;
        return Math.exp(-0.5 * z * z);
    }

    var xMin = Infinity, xMax = -Infinity;
    for (var i = 0; i < estimates.length; i++) {
        var lo = estimates[i].mu - 3.5 * estimates[i].sigma;
        var hi = estimates[i].mu + 3.5 * estimates[i].sigma;
        if (lo < xMin) xMin = lo;
        if (hi > xMax) xMax = hi;
    }
    if (answer !== null) {
        if (answer < xMin) xMin = answer - (xMax - answer) * 0.1;
        if (answer > xMax) xMax = answer + (answer - xMin) * 0.1;
    }
    var xPad = (xMax - xMin) * 0.05;
    xMin -= xPad;
    xMax += xPad;

    var N = 200;
    var xs = [];
    var dx = (xMax - xMin) / (N - 1);
    for (var i = 0; i < N; i++) xs.push(xMin + i * dx);

    var minDisplaySigma = (xMax - xMin) / 40;
    var indivCurves = [];
    var mixture = new Array(N).fill(0);
    for (var e = 0; e < estimates.length; e++) {
        var dSigma = Math.max(estimates[e].sigma, minDisplaySigma);
        var curve = [];
        for (var i = 0; i < N; i++) {
            var y = bell(xs[i], estimates[e].mu, dSigma);
            curve.push(y);
            mixture[i] += y;
        }
        indivCurves.push(curve);
    }
    for (var i = 0; i < N; i++) mixture[i] /= estimates.length;

    var yMax = 0;
    for (var i = 0; i < N; i++) {
        if (mixture[i] > yMax) yMax = mixture[i];
        for (var e = 0; e < indivCurves.length; e++) {
            if (indivCurves[e][i] > yMax) yMax = indivCurves[e][i];
        }
    }
    yMax *= 1.1;

    function sx(x) { return pad.left + (x - xMin) / (xMax - xMin) * plotW; }
    function sy(y) { return pad.top + plotH - (y / yMax) * plotH; }

    function buildPath(ys) {
        var px = [], py = [];
        for (var i = 0; i < N; i++) { px.push(sx(xs[i])); py.push(sy(ys[i])); }
        var d = "M" + px[0] + "," + py[0];
        for (var i = 1; i < N; i++) {
            var t0x, t0y, t1x, t1y;
            if (i === 1) { t0x = px[1] - px[0]; t0y = py[1] - py[0]; }
            else { t0x = 0.5 * (px[i] - px[i - 2]); t0y = 0.5 * (py[i] - py[i - 2]); }
            if (i === N - 1) { t1x = px[N - 1] - px[N - 2]; t1y = py[N - 1] - py[N - 2]; }
            else { t1x = 0.5 * (px[i + 1] - px[i - 1]); t1y = 0.5 * (py[i + 1] - py[i - 1]); }
            var cp1x = px[i - 1] + t0x / 3;
            var cp1y = py[i - 1] + t0y / 3;
            var cp2x = px[i] - t1x / 3;
            var cp2y = py[i] - t1y / 3;
            d += "C" + cp1x + "," + cp1y + "," + cp2x + "," + cp2y + "," + px[i] + "," + py[i];
        }
        return d;
    }

    function buildFilledPath(ys) {
        var d = buildPath(ys);
        d += "L" + sx(xs[N - 1]) + "," + sy(0) + "L" + sx(xs[0]) + "," + sy(0) + "Z";
        return d;
    }

    var ns = "http://www.w3.org/2000/svg";
    svg.innerHTML = "";
    svg.setAttribute("shape-rendering", "geometricPrecision");

    for (var e = 0; e < indivCurves.length; e++) {
        var path = document.createElementNS(ns, "path");
        path.setAttribute("d", buildPath(indivCurves[e]));
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "rgba(99, 102, 241, 0.2)");
        path.setAttribute("stroke-width", "1.5");
        svg.appendChild(path);
    }

    var fill = document.createElementNS(ns, "path");
    fill.setAttribute("d", buildFilledPath(mixture));
    fill.setAttribute("fill", "rgba(99, 102, 241, 0.1)");
    fill.setAttribute("stroke", "none");
    svg.appendChild(fill);

    var line = document.createElementNS(ns, "path");
    line.setAttribute("d", buildPath(mixture));
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "#4f46e5");
    line.setAttribute("stroke-width", "3");
    svg.appendChild(line);

    var axis = document.createElementNS(ns, "line");
    axis.setAttribute("x1", pad.left);
    axis.setAttribute("y1", sy(0));
    axis.setAttribute("x2", W - pad.right);
    axis.setAttribute("y2", sy(0));
    axis.setAttribute("stroke", "#cbd5e1");
    axis.setAttribute("stroke-width", "1");
    svg.appendChild(axis);

    var tickCount = 5;
    var range = xMax - xMin;
    var rawStep = range / tickCount;
    var mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var steps = [1, 2, 2.5, 5, 10];
    var step = mag;
    for (var i = 0; i < steps.length; i++) {
        if (steps[i] * mag >= rawStep) { step = steps[i] * mag; break; }
    }
    var tickStart = Math.ceil(xMin / step) * step;
    for (var tv = tickStart; tv <= xMax; tv += step) {
        var tx = sx(tv);
        var tick = document.createElementNS(ns, "line");
        tick.setAttribute("x1", tx);
        tick.setAttribute("y1", sy(0));
        tick.setAttribute("x2", tx);
        tick.setAttribute("y2", sy(0) + 6);
        tick.setAttribute("stroke", "#94a3b8");
        tick.setAttribute("stroke-width", "1");
        svg.appendChild(tick);

        var label = document.createElementNS(ns, "text");
        label.setAttribute("x", tx);
        label.setAttribute("y", sy(0) + 24);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "#64748b");
        label.setAttribute("font-size", "13");
        label.setAttribute("font-family", "'JetBrains Mono', monospace");
        label.textContent = tv % 1 === 0 ? tv.toLocaleString() : tv.toFixed(1);
        svg.appendChild(label);
    }

    if (unit) {
        var unitLabel = document.createElementNS(ns, "text");
        unitLabel.setAttribute("x", W - pad.right);
        unitLabel.setAttribute("y", sy(0) + 44);
        unitLabel.setAttribute("text-anchor", "end");
        unitLabel.setAttribute("fill", "#94a3b8");
        unitLabel.setAttribute("font-size", "13");
        unitLabel.setAttribute("font-family", "'Space Grotesk', sans-serif");
        unitLabel.textContent = unit;
        svg.appendChild(unitLabel);
    }

    if (answer !== null) {
        var ax = sx(answer);

        var ansLine = document.createElementNS(ns, "line");
        ansLine.setAttribute("x1", ax);
        ansLine.setAttribute("y1", pad.top);
        ansLine.setAttribute("x2", ax);
        ansLine.setAttribute("y2", sy(0));
        ansLine.setAttribute("stroke", "#059669");
        ansLine.setAttribute("stroke-width", "2.5");
        ansLine.setAttribute("stroke-dasharray", "8,4");
        svg.appendChild(ansLine);

        var ansLabel = document.createElementNS(ns, "text");
        ansLabel.setAttribute("x", ax);
        ansLabel.setAttribute("y", pad.top - 6);
        ansLabel.setAttribute("text-anchor", "middle");
        ansLabel.setAttribute("fill", "#059669");
        ansLabel.setAttribute("font-size", "14");
        ansLabel.setAttribute("font-weight", "600");
        ansLabel.setAttribute("font-family", "'JetBrains Mono', monospace");
        ansLabel.textContent = (answer % 1 === 0 ? answer.toLocaleString() : answer.toFixed(1)) + (unit ? " " + unit : "");
        svg.appendChild(ansLabel);
    }
}

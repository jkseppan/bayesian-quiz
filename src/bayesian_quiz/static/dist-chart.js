// Pure function: compute a robust x-range for the estimates so a single wild
// outlier can't stretch the axis. Returns {xMin, xMax} already 5%-padded.
// `answer` is unioned into the range when it is a finite number (pass null to
// keep the pure crowd view). No DOM access here so it is unit-testable.
function computeRobustRange(estimates, answer) {
    var n = estimates.length;
    if (n === 0) return {xMin: -1, xMax: 1};

    var los = [], his = [], mus = [];
    for (var i = 0; i < n; i++) {
        var mu = estimates[i].mu;
        var sigma = estimates[i].sigma;
        los.push(mu - 2.5 * sigma);
        his.push(mu + 2.5 * sigma);
        mus.push(mu);
    }

    function sortedNum(arr) {
        return arr.slice().sort(function (a, b) { return a - b; });
    }
    // Simple sorted-index percentile (p in [0,1]).
    function pct(sorted, p) {
        var idx = Math.round(p * (sorted.length - 1));
        if (idx < 0) idx = 0;
        if (idx > sorted.length - 1) idx = sorted.length - 1;
        return sorted[idx];
    }
    function median(arr) {
        var s = sortedNum(arr);
        var mid = Math.floor(s.length / 2);
        return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
    }

    var xMin, xMax;
    if (n >= 8) {
        // Trim lone outliers: 10th pct of lower bounds, 90th pct of upper bounds.
        xMin = pct(sortedNum(los), 0.10);
        xMax = pct(sortedNum(his), 0.90);
    } else {
        xMin = Math.min.apply(null, los);
        xMax = Math.max.apply(null, his);
    }

    // Always widen the frame to include the median of the mu values.
    var medMu = median(mus);
    if (medMu < xMin) xMin = medMu;
    if (medMu > xMax) xMax = medMu;

    // Guard degenerate spans (e.g. all estimates identical / sigma == 0).
    if (!(xMax > xMin)) {
        var center = (xMin + xMax) / 2;
        var maxSigma = 0;
        for (var j = 0; j < n; j++) {
            if (estimates[j].sigma > maxSigma) maxSigma = estimates[j].sigma;
        }
        var padAmt = maxSigma > 0 ? maxSigma : Math.max(1, Math.abs(center) * 0.05);
        xMin = center - padAmt;
        xMax = center + padAmt;
    }

    // Union the answer in (when it must be included) then re-pad below.
    if (answer !== null && answer !== undefined && isFinite(answer)) {
        if (answer < xMin) xMin = answer;
        if (answer > xMax) xMax = answer;
    }

    // Keep the existing 5% padding behavior.
    var xPad = (xMax - xMin) * 0.05;
    xMin -= xPad;
    xMax += xPad;

    return {xMin: xMin, xMax: xMax};
}

// renderDistChart(svgId, estimates, unit, answer, drawAnswer, options)
// options (optional): {xMin, xMax} explicit range override so the same renderer
// can be driven frame-by-frame for the reveal zoom animation. When omitted the
// robust range is derived from the estimates (and answer, when present).
function renderDistChart(svgId, estimates, unit, answer, drawAnswer, options) {
    if (drawAnswer === undefined) drawAnswer = true;
    if (options === undefined) options = null;
    var svg = document.getElementById(svgId);
    if (!svg || estimates.length === 0) return;

    var W = 800, H = 320;
    var pad = {top: 44, right: 40, bottom: 50, left: 40};
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;

    function bell(x, mu, sigma) {
        var z = (x - mu) / sigma;
        return Math.exp(-0.5 * z * z);
    }

    var xMin, xMax;
    if (options && options.xMin !== undefined && options.xMax !== undefined) {
        // Explicit (already-padded) range override for frame-by-frame drawing.
        xMin = options.xMin;
        xMax = options.xMax;
    } else {
        var robust = computeRobustRange(estimates, answer);
        xMin = robust.xMin;
        xMax = robust.xMax;
    }

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
        var d = "M" + sx(xs[0]) + "," + sy(ys[0]);
        for (var i = 1; i < N; i++) d += "L" + sx(xs[i]) + "," + sy(ys[i]);
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

    if (answer !== null && drawAnswer) {
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
        ansLabel.setAttribute("font-size", "32");
        ansLabel.setAttribute("font-weight", "600");
        ansLabel.setAttribute("font-family", "'JetBrains Mono', monospace");
        ansLabel.textContent = (answer % 1 === 0 ? answer.toLocaleString() : answer.toFixed(1)) + (unit ? " " + unit : "");
        svg.appendChild(ansLabel);
    }
}

// Node/CommonJS export for unit testing (no-op in the browser).
if (typeof module !== "undefined" && module.exports) {
    module.exports = { renderDistChart: renderDistChart, computeRobustRange: computeRobustRange };
}

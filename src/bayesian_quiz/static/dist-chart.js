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

    // All guesses non-negative (and the answer too, when shown): don't let the
    // 2.5-sigma tails drag the axis below zero for an obviously positive
    // quantity (years, GWh, counts...).
    var minMu = Math.min.apply(null, mus);
    var answerNonNeg = answer === null || answer === undefined || answer >= 0;
    if (minMu >= 0 && answerNonNeg && xMin < 0) xMin = 0;

    // Union the answer in (when it must be included) then re-pad below.
    if (answer !== null && answer !== undefined && isFinite(answer)) {
        if (answer < xMin) xMin = answer;
        if (answer > xMax) xMax = answer;
    }

    // Keep the existing 5% padding behavior (but never pad a clamped-at-zero
    // axis back below zero).
    var clampedZero = xMin === 0;
    var xPad = (xMax - xMin) * 0.05;
    xMin -= xPad;
    xMax += xPad;
    if (clampedZero && xMin < 0) xMin = 0;

    return {xMin: xMin, xMax: xMax};
}

// Pick the smallest "nice" step that yields at most maxTicks ticks over the
// range (i.e. the densest axis that still fits).
function niceTickStep(range, maxTicks) {
    if (!(maxTicks >= 1)) maxTicks = 1;
    var minStep = range / maxTicks;
    var mag = Math.pow(10, Math.floor(Math.log10(minStep)));
    var mults = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < mults.length; i++) {
        var s = mults[i] * mag;
        if (s >= minStep) return s;
    }
    return 10 * mag;
}

// Format a tick value given the tick step: enough decimals to distinguish
// neighbouring ticks, compact SI suffixes for large magnitudes, and no "-0".
function formatTick(value, step) {
    if (Math.abs(value) < step * 1e-6) return "0";
    var abs = Math.abs(value);
    if (step >= 1000 && abs >= 10000) {
        var divisor, suffix;
        if (abs >= 1e9) { divisor = 1e9; suffix = "B"; }
        else if (abs >= 1e6) { divisor = 1e6; suffix = "M"; }
        else { divisor = 1e3; suffix = "k"; }
        var d = Math.max(0, -Math.floor(Math.log10(step / divisor) + 1e-9));
        return (value / divisor).toFixed(Math.min(d, 2)) + suffix;
    }
    if (step >= 1) {
        return Math.round(value).toLocaleString();
    }
    var decimals = Math.min(8, Math.ceil(-Math.log10(step) - 1e-9));
    return value.toFixed(decimals);
}

// Format the revealed answer for the in-chart label: compact but precise
// enough to be meaningful at any magnitude.
function formatAnswer(value) {
    var abs = Math.abs(value);
    if (abs >= 1e5) {
        var divisor, suffix;
        if (abs >= 1e9) { divisor = 1e9; suffix = "B"; }
        else if (abs >= 1e6) { divisor = 1e6; suffix = "M"; }
        else { divisor = 1e3; suffix = "k"; }
        return parseFloat((value / divisor).toPrecision(3)) + suffix;
    }
    if (value % 1 === 0) return value.toLocaleString();
    if (abs >= 1) return value.toFixed(1);
    return parseFloat(value.toPrecision(3)).toString();
}

// renderDistChart(svgId, estimates, unit, answer, drawAnswer, options)
// options (all optional):
//   xMin, xMax: explicit (already-padded) range override so the same renderer
//     can be driven frame-by-frame for the reveal zoom animation. When omitted
//     the robust range is derived from the estimates (and answer, when present).
//   fontScale: multiplier for axis tick / unit label sizes (small screens)
//   own: {mu, sigma} — highlight one estimate as "you"
//   fit: size the drawing to the SVG element's current client box instead of
//     the fixed 800x320 viewBox (projector: fills whatever space it is given,
//     with font sizes scaled to the rendered pixels).
function renderDistChart(svgId, estimates, unit, answer, drawAnswer, options) {
    if (drawAnswer === undefined) drawAnswer = true;
    if (answer === undefined) answer = null;
    options = options || {};
    var fontScale = options.fontScale || 1;
    var own = options.own || null;
    var fit = !!options.fit;
    var svg = document.getElementById(svgId);
    if (!svg || estimates.length === 0) return;

    var W = 800, H = 320;
    if (fit) {
        var box = svg.getBoundingClientRect();
        if (box.width > 10 && box.height > 10) {
            W = Math.round(box.width);
            H = Math.round(box.height);
        }
        svg.setAttribute("viewBox", "0 0 " + W + " " + H);
        svg.style.overflow = "visible";
    }

    // Typography: fixed sizes for the legacy 800x320 participant chart,
    // proportional-to-pixels for fit mode (projector).
    var tickFont, unitFont, ansFont, youFont, aggStroke, indivStroke;
    if (fit) {
        tickFont = Math.max(20, Math.round(H * 0.045)) * fontScale;
        unitFont = tickFont;
        ansFont = Math.max(28, Math.round(H * 0.075)) * fontScale;
        youFont = Math.max(22, Math.round(H * 0.055)) * fontScale;
        aggStroke = Math.max(3, H * 0.008);
        indivStroke = Math.max(1.5, H * 0.0035);
    } else {
        tickFont = 13 * fontScale;
        unitFont = 13 * fontScale;
        ansFont = 32;
        youFont = 22;
        aggStroke = 3;
        indivStroke = 1.5;
    }

    var pad = fit
        ? {top: (options.hideAnswerLabel ? Math.round(tickFont * 1.6) : ansFont) + 16,
           right: 20, bottom: tickFont * 2.4, left: 20}
        : {top: 44, right: 40, bottom: 50, left: 40};
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

    var N = fit ? 400 : 200;
    var xs = [];
    var dx = (xMax - xMin) / (N - 1);
    for (var i = 0; i < N; i++) xs.push(xMin + i * dx);

    var minDisplaySigma = (xMax - xMin) / 40;
    var indivCurves = [];
    var mixture = new Array(N).fill(0);
    var indivPeak = 0;
    for (var e = 0; e < estimates.length; e++) {
        var dSigma = Math.max(estimates[e].sigma, minDisplaySigma);
        var curve = [];
        for (var i = 0; i < N; i++) {
            // True pdf shape (the common 1/sqrt(2*pi) factor cancels in the
            // global rescale below): narrow guesses are genuinely taller.
            var y = bell(xs[i], estimates[e].mu, dSigma) / dSigma;
            curve.push(y);
            mixture[i] += y;
            if (y > indivPeak) indivPeak = y;
        }
        indivCurves.push(curve);
    }
    for (var i = 0; i < N; i++) mixture[i] /= estimates.length;

    // One common scale, anchored so the aggregate peaks at 92% of the plot
    // height. Individual curves share that scale (true relative heights);
    // if the tallest one would overshoot the plot, all individuals are
    // shrunk together just enough to fit.
    var mixPeak = 0;
    for (var i = 0; i < N; i++) if (mixture[i] > mixPeak) mixPeak = mixture[i];
    if (mixPeak <= 0) mixPeak = 1;
    var mixScale = 0.92 / mixPeak;
    var indivScale = mixScale;
    if (indivPeak * mixScale > 0.98) indivScale = 0.98 / indivPeak;

    function sx(x) { return pad.left + (x - xMin) / (xMax - xMin) * plotW; }
    function sy(y) { return pad.top + plotH - Math.min(1, y) * plotH; }

    function buildPath(ys, scale) {
        var d = "M" + sx(xs[0]) + "," + sy(ys[0] * scale);
        for (var i = 1; i < N; i++) d += "L" + sx(xs[i]) + "," + sy(ys[i] * scale);
        return d;
    }

    function buildFilledPath(ys, scale) {
        var d = buildPath(ys, scale);
        d += "L" + sx(xs[N - 1]) + "," + sy(0) + "L" + sx(xs[0]) + "," + sy(0) + "Z";
        return d;
    }

    var ns = "http://www.w3.org/2000/svg";
    svg.innerHTML = "";
    svg.setAttribute("shape-rendering", "geometricPrecision");

    // White halo behind text so labels stay readable on top of curves.
    function halo(el) {
        el.setAttribute("stroke", "#ffffff");
        el.setAttribute("stroke-width", Math.max(4, tickFont * 0.28));
        el.setAttribute("paint-order", "stroke");
        el.setAttribute("stroke-linejoin", "round");
        return el;
    }

    // With many players, fade the individual curves so they read as texture
    // rather than a solid mat; the aggregate carries the signal.
    var nCurves = indivCurves.length;
    var indivOpacity = nCurves <= 25 ? 0.30 : Math.max(0.05, 7.5 / nCurves);

    for (var e = 0; e < indivCurves.length; e++) {
        var path = document.createElementNS(ns, "path");
        path.setAttribute("d", buildPath(indivCurves[e], indivScale));
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "rgba(99, 102, 241, " + indivOpacity.toFixed(3) + ")");
        path.setAttribute("stroke-width", indivStroke);
        svg.appendChild(path);
    }

    var fill = document.createElementNS(ns, "path");
    fill.setAttribute("d", buildFilledPath(mixture, mixScale));
    fill.setAttribute("fill", "rgba(99, 102, 241, 0.12)");
    fill.setAttribute("stroke", "none");
    svg.appendChild(fill);

    var line = document.createElementNS(ns, "path");
    line.setAttribute("d", buildPath(mixture, mixScale));
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "#4f46e5");
    line.setAttribute("stroke-width", aggStroke);
    svg.appendChild(line);

    if (own && isFinite(own.mu) && isFinite(own.sigma)) {
        var ownSigma = Math.max(own.sigma, minDisplaySigma);
        var ownYs = [];
        for (var i = 0; i < N; i++) ownYs.push(bell(xs[i], own.mu, ownSigma) / ownSigma);
        var ownPath = document.createElementNS(ns, "path");
        ownPath.setAttribute("d", buildPath(ownYs, indivScale));
        ownPath.setAttribute("fill", "none");
        ownPath.setAttribute("stroke", "#7c3aed");
        ownPath.setAttribute("stroke-width", aggStroke);
        ownPath.setAttribute("stroke-dasharray", "6,4");
        svg.appendChild(ownPath);

        var ownPeakY = 0;
        for (var i = 0; i < N; i++) if (ownYs[i] > ownPeakY) ownPeakY = ownYs[i];
        var ownX = sx(own.mu);
        if (ownX >= pad.left && ownX <= W - pad.right) {
            var ownLabel = document.createElementNS(ns, "text");
            ownLabel.setAttribute("x", ownX);
            ownLabel.setAttribute("y", Math.max(tickFont, sy(Math.min(1, ownPeakY * indivScale)) - 8));
            ownLabel.setAttribute("text-anchor", "middle");
            ownLabel.setAttribute("fill", "#7c3aed");
            ownLabel.setAttribute("font-size", youFont);
            ownLabel.setAttribute("font-weight", "600");
            ownLabel.setAttribute("font-family", "'Space Grotesk', sans-serif");
            ownLabel.textContent = "you";
            svg.appendChild(halo(ownLabel));
        }
    }

    var axis = document.createElementNS(ns, "line");
    axis.setAttribute("x1", pad.left);
    axis.setAttribute("y1", sy(0));
    axis.setAttribute("x2", W - pad.right);
    axis.setAttribute("y2", sy(0));
    axis.setAttribute("stroke", "#cbd5e1");
    axis.setAttribute("stroke-width", fit ? 2 : 1);
    svg.appendChild(axis);

    // As many ticks as comfortably fit: estimate label width with a coarse
    // step first, then refine. Clamped to [3, 7].
    var step = niceTickStep(xMax - xMin, 5);
    var sampleLabel = formatTick(Math.abs(xMin) > Math.abs(xMax) ? xMin : xMax, step);
    var approxLabelW = (sampleLabel.length + 1) * tickFont * 0.62;
    var maxTicks = Math.max(3, Math.min(7, Math.floor(plotW / (approxLabelW * 1.7))));
    step = niceTickStep(xMax - xMin, maxTicks);

    var tickStart = Math.ceil(xMin / step) * step;
    var lastTv = tickStart;
    for (var tv = tickStart; tv <= xMax + step * 1e-6; tv += step) lastTv = tv;
    for (var tv = tickStart; tv <= xMax + step * 1e-6; tv += step) {
        var tx = sx(tv);
        var tick = document.createElementNS(ns, "line");
        tick.setAttribute("x1", tx);
        tick.setAttribute("y1", sy(0));
        tick.setAttribute("x2", tx);
        tick.setAttribute("y2", sy(0) + (fit ? 8 : 6));
        tick.setAttribute("stroke", "#94a3b8");
        tick.setAttribute("stroke-width", fit ? 2 : 1);
        svg.appendChild(tick);

        var label = document.createElementNS(ns, "text");
        label.setAttribute("x", tx);
        label.setAttribute("y", sy(0) + (fit ? tickFont * 1.5 : 24));
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "#475569");
        label.setAttribute("font-size", tickFont);
        label.setAttribute("font-family", "'JetBrains Mono', monospace");
        label.textContent = formatTick(tv, step) +
            (fit && unit && tv === lastTv ? "\u2009" + unit : "");
        svg.appendChild(halo(label));
    }

    if (unit && !fit) {
        var unitLabel = document.createElementNS(ns, "text");
        unitLabel.setAttribute("x", W - pad.right);
        unitLabel.setAttribute("y", sy(0) - (fit ? 10 : 8));
        unitLabel.setAttribute("text-anchor", "end");
        unitLabel.setAttribute("fill", "#64748b");
        unitLabel.setAttribute("font-size", unitFont);
        unitLabel.setAttribute("font-family", "'Space Grotesk', sans-serif");
        unitLabel.textContent = unit;
        svg.appendChild(halo(unitLabel));
    }

    if (answer !== null && drawAnswer) {
        var ax = sx(answer);

        var ansLine = document.createElementNS(ns, "line");
        ansLine.setAttribute("x1", ax);
        ansLine.setAttribute("y1", pad.top);
        ansLine.setAttribute("x2", ax);
        ansLine.setAttribute("y2", sy(0));
        ansLine.setAttribute("stroke", "#059669");
        ansLine.setAttribute("stroke-width", fit ? 4 : 2.5);
        ansLine.setAttribute("stroke-dasharray", "8,4");
        svg.appendChild(ansLine);

        // Projector reveal shows the exact answer as a headline, so the
        // in-chart label becomes a compact tag that just marks the line.
        var compact = !!options.hideAnswerLabel;
        var tagFont = compact ? Math.round(tickFont * 1.15) : ansFont;
        var ansText = compact
            ? formatAnswer(answer)
            : formatAnswer(answer) + (unit ? " " + unit : "");
        // Clamp the label horizontally so it never runs off either edge of
        // the drawing (the answer line itself can sit right at the edge).
        var halfW = ansText.length * tagFont * 0.31;
        var lx = Math.max(halfW + 4, Math.min(W - halfW - 4, ax));

        var ansLabel = document.createElementNS(ns, "text");
        ansLabel.setAttribute("x", lx);
        ansLabel.setAttribute("y", pad.top - 8);
        ansLabel.setAttribute("text-anchor", "middle");
        ansLabel.setAttribute("fill", "#059669");
        ansLabel.setAttribute("font-size", tagFont);
        ansLabel.setAttribute("font-weight", "600");
        ansLabel.setAttribute("font-family", "'JetBrains Mono', monospace");
        ansLabel.textContent = ansText;
        svg.appendChild(halo(ansLabel));
    }
}

// Node/CommonJS export for unit testing (no-op in the browser).
if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        renderDistChart: renderDistChart,
        computeRobustRange: computeRobustRange,
        niceTickStep: niceTickStep,
        formatTick: formatTick,
        formatAnswer: formatAnswer,
    };
}

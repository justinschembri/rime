// Observation unpacking — scalar instances and array-backed time series.

function escapeCsvField(value) {
    if (value === null || value === undefined) return '';
    const stringValue = String(value);
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
        return `"${stringValue.replace(/"/g, '""')}"`;
    }
    return stringValue;
}

function parseTimeRange(value) {
    if (!value) return null;
    if (value.includes('/')) {
        const [a, b] = value.split('/');
        const start = new Date(a);
        const end = new Date(b);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
        return { start, end };
    }
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return { start: d, end: d };
}

function coerceNumericResult(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

function isArrayResult(result) {
    return Array.isArray(result);
}

// Most recent sample: last element for array results, scalar otherwise.
function latestObservationResult(result) {
    if (result === null || result === undefined) return null;
    if (isArrayResult(result)) {
        if (result.length === 0) return null;
        return result[result.length - 1];
    }
    return result;
}

function formatLatestObservationResult(result, unitSymbol = '') {
    const latest = latestObservationResult(result);
    if (latest === null || latest === undefined) return '-';
    const numeric = coerceNumericResult(latest);
    const display = numeric !== null ? numeric : latest;
    return `${display}${unitSymbol ? ` ${unitSymbol}` : ''}`;
}

// Expand one STA Observation into chart points { x: Date, y: number }.
// When maxPoints is set, only the most recent samples are materialised.
function expandObservationToPoints(observation, maxPoints = null) {
    const range = parseTimeRange(observation.phenomenonTime);
    if (!range) return [];

    const result = observation.result;
    if (isArrayResult(result)) {
        if (result.length === 0) return [];

        let values = result;
        let rangeStart = range.start;
        const rangeEnd = range.end;

        if (maxPoints && result.length > maxPoints) {
            values = result.slice(-maxPoints);
            const startMs = range.start.getTime();
            const endMs = range.end.getTime();
            const deltaMs = result.length > 1 ? (endMs - startMs) / (result.length - 1) : 0;
            rangeStart = new Date(startMs + (result.length - values.length) * deltaMs);
        }

        const startMs = rangeStart.getTime();
        const endMs = rangeEnd.getTime();
        const points = [];

        if (values.length === 1) {
            const y = coerceNumericResult(values[0]);
            if (y !== null) points.push({ x: rangeEnd, y });
            return points;
        }

        const deltaMs = (endMs - startMs) / (values.length - 1);
        for (let i = 0; i < values.length; i += 1) {
            const y = coerceNumericResult(values[i]);
            if (y === null) continue;
            points.push({ x: new Date(startMs + i * deltaMs), y });
        }
        return points;
    }

    const y = coerceNumericResult(result);
    if (y === null) return [];
    return [{ x: range.end, y }];
}

function normalizeObservations(observations) {
    const points = [];
    for (const entry of observations || []) {
        points.push(...expandObservationToPoints(entry));
    }
    points.sort((a, b) => a.x.getTime() - b.x.getTime());
    return points;
}

function observationToCsvRows(observation) {
    const points = expandObservationToPoints(observation);
    if (points.length === 0) {
        return [[
            escapeCsvField(observation.phenomenonTime),
            escapeCsvField(observation.resultTime),
            escapeCsvField(observation.result),
        ].join(',')];
    }

    const resultTime = observation.resultTime || '';
    return points.map((point) => [
        escapeCsvField(point.x.toISOString()),
        escapeCsvField(resultTime),
        escapeCsvField(point.y),
    ].join(','));
}

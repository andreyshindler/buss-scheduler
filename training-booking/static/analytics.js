let analyticsWeeks = 12;

async function renderAnalytics() {
  await Promise.all([renderFillTrend(), renderTopUsers(), renderCancelTiming()]);
}

async function renderFillTrend() {
  const container = document.getElementById('chart-fill-trend');
  if (!container) return;
  container.innerHTML = '';

  try {
    const res = await apiFetch(`/api/analytics/fill-trend?weeks=${analyticsWeeks}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.length) { container.innerHTML = `<p class="no-data">${t('no_data')}</p>`; return; }

    const margin = { top: 20, right: 20, bottom: 40, left: 50 };
    const width = container.clientWidth - margin.left - margin.right || 400;
    const height = 220 - margin.top - margin.bottom;

    const svg = d3.select(container).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scalePoint().domain(data.map(d => d.week)).range([0, width]).padding(0.2);
    const y = d3.scaleLinear().domain([0, 100]).range([height, 0]);

    // Area
    const area = d3.area()
      .x(d => x(d.week))
      .y0(height)
      .y1(d => y(d.fill_pct))
      .curve(d3.curveCatmullRom.alpha(0.5));

    svg.append('path').datum(data)
      .attr('fill', 'rgba(37,99,235,0.15)')
      .attr('d', area);

    // Line
    const line = d3.line()
      .x(d => x(d.week))
      .y(d => y(d.fill_pct))
      .curve(d3.curveCatmullRom.alpha(0.5));

    svg.append('path').datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#2563eb')
      .attr('stroke-width', 2.5)
      .attr('d', line);

    // Dots + tooltip
    const tooltip = d3.select(container).append('div')
      .attr('class', 'chart-tooltip')
      .style('opacity', 0)
      .style('position', 'absolute')
      .style('background', '#1e293b')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('pointer-events', 'none');

    svg.selectAll('circle').data(data).enter().append('circle')
      .attr('cx', d => x(d.week))
      .attr('cy', d => y(d.fill_pct))
      .attr('r', 4)
      .attr('fill', '#2563eb')
      .on('mouseover', (event, d) => {
        tooltip.transition().duration(100).style('opacity', 1);
        tooltip.html(`${d.week}<br>${d.fill_pct}%`)
          .style('left', (event.offsetX + 10) + 'px')
          .style('top', (event.offsetY - 20) + 'px');
      })
      .on('mouseout', () => tooltip.transition().duration(200).style('opacity', 0));

    // Axes
    svg.append('g').attr('transform', `translate(0,${height})`).call(d3.axisBottom(x).tickValues(data.filter((_, i) => i % Math.ceil(data.length / 6) === 0).map(d => d.week)));
    svg.append('g').call(d3.axisLeft(y).tickFormat(d => d + '%').ticks(5));
  } catch (e) {
    container.innerHTML = `<p class="no-data">${t('no_data')}</p>`;
  }
}

async function renderTopUsers() {
  const container = document.getElementById('chart-top-users');
  if (!container) return;
  container.innerHTML = '';

  try {
    const res = await apiFetch('/api/analytics/top-users');
    if (!res.ok) { container.style.display = 'none'; return; }
    const data = await res.json();
    if (!data.length) { container.innerHTML = `<p class="no-data">${t('no_data')}</p>`; return; }

    const margin = { top: 10, right: 60, bottom: 20, left: 120 };
    const width = container.clientWidth - margin.left - margin.right || 300;
    const height = data.length * 32;

    const svg = d3.select(container).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, d3.max(data, d => d.count)]).range([0, width]);
    const y = d3.scaleBand().domain(data.map(d => d.name)).range([0, height]).padding(0.2);

    const colorScale = d3.scaleSequential(d3.interpolateBlues).domain([0, data.length]);

    svg.selectAll('rect').data(data).enter().append('rect')
      .attr('x', 0)
      .attr('y', d => y(d.name))
      .attr('width', d => x(d.count))
      .attr('height', y.bandwidth())
      .attr('fill', (d, i) => colorScale(i + 2))
      .attr('rx', 4);

    svg.selectAll('.val-label').data(data).enter().append('text')
      .attr('class', 'val-label')
      .attr('x', d => x(d.count) + 5)
      .attr('y', d => y(d.name) + y.bandwidth() / 2 + 4)
      .attr('fill', '#374151')
      .attr('font-size', '12px')
      .text(d => d.count);

    svg.append('g').call(d3.axisLeft(y));
  } catch (e) {
    container.innerHTML = `<p class="no-data">${t('no_data')}</p>`;
  }
}

async function renderCancelTiming() {
  const container = document.getElementById('chart-cancel-timing');
  if (!container) return;
  container.innerHTML = '';

  try {
    const res = await apiFetch('/api/analytics/cancel-timing');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.total) { container.innerHTML = `<p class="no-data">${t('no_data')}</p>`; return; }

    const size = 200;
    const radius = size / 2;
    const colors = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'];

    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${size + 200} ${size}`)
      .style('max-width', '500px');

    const g = svg.append('g').attr('transform', `translate(${radius},${radius})`);

    const pie = d3.pie().value(d => d.count).sort(null);
    const arc = d3.arc().innerRadius(radius * 0.5).outerRadius(radius * 0.9);

    const tooltip = d3.select(container).append('div')
      .attr('class', 'chart-tooltip')
      .style('opacity', 0).style('position', 'absolute')
      .style('background', '#1e293b').style('color', '#fff')
      .style('padding', '6px 10px').style('border-radius', '6px')
      .style('font-size', '12px').style('pointer-events', 'none');

    const arcs = g.selectAll('arc').data(pie(data.buckets)).enter().append('g');

    arcs.append('path')
      .attr('d', arc)
      .attr('fill', (d, i) => colors[i % colors.length])
      .on('mouseover', (event, d) => {
        tooltip.transition().duration(100).style('opacity', 1);
        tooltip.html(`${d.data.label}: ${d.data.count} (${d.data.pct}%)`)
          .style('left', (event.offsetX + 10) + 'px')
          .style('top', (event.offsetY - 20) + 'px');
      })
      .on('mouseout', () => tooltip.transition().duration(200).style('opacity', 0));

    // Center text
    g.append('text').attr('text-anchor', 'middle').attr('dy', '-0.3em')
      .attr('font-size', '14px').attr('font-weight', 'bold').attr('fill', '#1e293b')
      .text(data.avg_hours + 'h');
    g.append('text').attr('text-anchor', 'middle').attr('dy', '1em')
      .attr('font-size', '10px').attr('fill', '#6b7280')
      .text(t('analytics_avg_hours').split(' ').slice(0, 2).join(' '));

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${size + 10}, 10)`);
    data.buckets.forEach((b, i) => {
      const row = legend.append('g').attr('transform', `translate(0, ${i * 28})`);
      row.append('rect').attr('width', 14).attr('height', 14).attr('rx', 3).attr('fill', colors[i % colors.length]);
      row.append('text').attr('x', 20).attr('y', 11).attr('font-size', '12px').attr('fill', '#374151')
        .text(`${b.label}: ${b.count} (${b.pct}%)`);
    });
  } catch (e) {
    container.innerHTML = `<p class="no-data">${t('no_data')}</p>`;
  }
}

function setAnalyticsWeeks(weeks) {
  analyticsWeeks = weeks;
  renderFillTrend();
}

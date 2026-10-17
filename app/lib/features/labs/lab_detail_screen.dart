import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:go_router/go_router.dart';
import 'lab_chart_controller.dart';
import 'labs_controller.dart';

class LabDetailScreen extends ConsumerWidget {
  final String testName;

  const LabDetailScreen({super.key, required this.testName});

  Color _getFlagColor(String? flag) {
    switch (flag?.toLowerCase()) {
      case 'high':
      case 'critical':
        return Colors.red;
      case 'low':
        return Colors.orange;
      case 'normal':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chartAsync = ref.watch(labChartProvider(testName));
    final favourites = ref.watch(labFavouritesProvider);
    final activeRange = ref.watch(activeTimeRangeProvider);
    final isFav = favourites.contains(testName);

    return Scaffold(
      appBar: AppBar(
        title: Text(testName, style: const TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: Icon(
              isFav ? Icons.star : Icons.star_border,
              color: isFav ? Colors.amber : null,
            ),
            tooltip: isFav ? 'Unpin favorite' : 'Pin favorite',
            onPressed: () => ref.read(labFavouritesProvider.notifier).toggle(testName),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reload',
            onPressed: () => ref.read(labChartProvider(testName).notifier).reload(),
          ),
        ],
      ),
      body: chartAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, color: Colors.red, size: 48),
              const SizedBox(height: 12),
              Text('Error loading chart: $err'),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.read(labChartProvider(testName).notifier).reload(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (chartData) {
          return SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Time Range Filter Chips
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: ['3M', '6M', '1Y', 'ALL'].map((r) {
                    final selected = activeRange == r;
                    return Padding(
                      padding: const EdgeInsets.only(left: 6),
                      child: ChoiceChip(
                        label: Text(r, style: TextStyle(fontSize: 12, fontWeight: selected ? FontWeight.bold : FontWeight.normal)),
                        selected: selected,
                        onSelected: (val) {
                          if (val) {
                            ref.read(activeTimeRangeProvider.notifier).state = r;
                          }
                        },
                      ),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 12),

                // Chart or Empty State
                if (chartData.points.isEmpty) ...[
                  Card(
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Center(
                        child: Column(
                          children: [
                            const Icon(Icons.show_chart, size: 48, color: Colors.grey),
                            const SizedBox(height: 12),
                            Text(
                              'No readings available for $testName',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Try selecting a wider date range or upload more reports.',
                              style: TextStyle(color: Colors.grey, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ] else ...[
                  _buildChartCard(context, chartData),
                ],
                const SizedBox(height: 24),

                // HISTORY TABLE
                if (chartData.points.isNotEmpty) ...[
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'RECORD HISTORY',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                          color: Colors.grey,
                        ),
                      ),
                      Text(
                        '${chartData.points.length} record${chartData.points.length > 1 ? 's' : ''}',
                        style: const TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Card(
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      side: BorderSide(color: Colors.grey.shade300),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: SizedBox(
                      width: double.infinity,
                      child: DataTable(
                        columnSpacing: 16,
                        headingRowColor: WidgetStateProperty.all(Colors.grey.shade100),
                        columns: const [
                          DataColumn(label: Text('Date', style: TextStyle(fontWeight: FontWeight.bold))),
                          DataColumn(label: Text('Value', style: TextStyle(fontWeight: FontWeight.bold))),
                          DataColumn(label: Text('Flag', style: TextStyle(fontWeight: FontWeight.bold))),
                          DataColumn(label: Text('Source', style: TextStyle(fontWeight: FontWeight.bold))),
                        ],
                        rows: chartData.points.reversed.map((p) {
                          final dateStr =
                              '${p.date.year}-${p.date.month.toString().padLeft(2, '0')}-${p.date.day.toString().padLeft(2, '0')}';
                          final valStr = '${p.value} ${chartData.unit ?? ''}';
                          return DataRow(
                            cells: [
                              DataCell(Text(dateStr)),
                              DataCell(Text(valStr, style: const TextStyle(fontWeight: FontWeight.bold))),
                              DataCell(
                                p.flag != null
                                    ? Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: _getFlagColor(p.flag).withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(4),
                                        ),
                                        child: Text(
                                          p.flag!.toUpperCase(),
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                            color: _getFlagColor(p.flag),
                                          ),
                                        ),
                                      )
                                    : const Text('-'),
                              ),
                              DataCell(
                                TextButton.icon(
                                  icon: const Icon(Icons.description_outlined, size: 14),
                                  label: Text('Doc #${p.documentId}', style: const TextStyle(fontSize: 12)),
                                  onPressed: () {
                                    context.go('/documents/${p.documentId}');
                                  },
                                ),
                              ),
                            ],
                          );
                        }).toList(),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildChartCard(BuildContext context, LabChartData data) {
    final points = data.points;
    final unit = data.unit ?? '';

    // Calculate Y range bounds with padding
    final allValues = points.map((p) => p.value).toList();
    if (data.refLow != null) allValues.add(data.refLow!);
    if (data.refHigh != null) allValues.add(data.refHigh!);

    final minYVal = allValues.reduce((a, b) => a < b ? a : b);
    final maxYVal = allValues.reduce((a, b) => a > b ? a : b);
    final yPad = (maxYVal - minYVal) * 0.15 > 0 ? (maxYVal - minYVal) * 0.15 : 1.0;
    final minY = (minYVal - yPad).floorToDouble();
    final maxY = (maxYVal + yPad).ceilToDouble();

    // Map points to FlSpot index (0 .. points.length - 1)
    final spots = List.generate(points.length, (i) => FlSpot(i.toDouble(), points[i].value));

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (data.refLow != null && data.refHigh != null) ...[
              Row(
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: Colors.green.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(3),
                      border: Border.all(color: Colors.green),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Normal Reference Band: ${data.refLow} – ${data.refHigh} $unit',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.green),
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
            SizedBox(
              height: 220,
              child: LineChart(
                LineChartData(
                  minY: minY,
                  maxY: maxY,
                  minX: 0,
                  maxX: (points.length - 1).toDouble() > 0 ? (points.length - 1).toDouble() : 1.0,
                  rangeAnnotations: RangeAnnotations(
                    horizontalRangeAnnotations: (data.refLow != null && data.refHigh != null)
                        ? [
                            HorizontalRangeAnnotation(
                              y1: data.refLow!,
                              y2: data.refHigh!,
                              color: Colors.green.withValues(alpha: 0.12),
                            ),
                          ]
                        : [],
                  ),
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    getDrawingHorizontalLine: (_) => FlLine(color: Colors.grey.shade200, strokeWidth: 1),
                  ),
                  borderData: FlBorderData(
                    show: true,
                    border: Border.all(color: Colors.grey.shade300),
                  ),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 42,
                        getTitlesWidget: (val, meta) {
                          if (val == meta.min || val == meta.max) return const SizedBox.shrink();
                          return Text(val.toStringAsFixed(1), style: const TextStyle(fontSize: 10, color: Colors.grey));
                        },
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 28,
                        interval: 1,
                        getTitlesWidget: (val, meta) {
                          final idx = val.toInt();
                          if (idx >= 0 && idx < points.length) {
                            final d = points[idx].date;
                            return Padding(
                              padding: const EdgeInsets.only(top: 4.0),
                              child: Text(
                                '${d.month}/${d.day}',
                                style: const TextStyle(fontSize: 10, color: Colors.grey),
                              ),
                            );
                          }
                          return const SizedBox.shrink();
                        },
                      ),
                    ),
                  ),
                  lineBarsData: [
                    LineChartBarData(
                      spots: spots,
                      isCurved: false,
                      color: Theme.of(context).colorScheme.primary,
                      barWidth: 3,
                      isStrokeCapRound: true,
                      dotData: FlDotData(
                        show: true,
                        getDotPainter: (spot, percent, barData, index) {
                          final flag = points[index].flag;
                          return FlDotCirclePainter(
                            radius: 5,
                            color: _getFlagColor(flag),
                            strokeWidth: 2,
                            strokeColor: Colors.white,
                          );
                        },
                      ),
                    ),
                  ],
                  lineTouchData: LineTouchData(
                    touchTooltipData: LineTouchTooltipData(
                      getTooltipItems: (touchedSpots) {
                        return touchedSpots.map((spot) {
                          final idx = spot.spotIndex;
                          final p = points[idx];
                          final d = p.date;
                          final dateStr = '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
                          final flagStr = p.flag != null ? ' (${p.flag!.toUpperCase()})' : '';
                          return LineTooltipItem(
                            '$dateStr\n${spot.y} $unit$flagStr',
                            const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                          );
                        }).toList();
                      },
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

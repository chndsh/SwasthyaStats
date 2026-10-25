import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/connectivity.dart';
import '../navigation/user_menu_button.dart';
import 'labs_controller.dart';
import 'lab_model.dart';

class LabsScreen extends ConsumerStatefulWidget {
  const LabsScreen({super.key});

  @override
  ConsumerState<LabsScreen> createState() => _LabsScreenState();
}

class _LabsScreenState extends ConsumerState<LabsScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _filter = '';
  bool _filterAbnormalOnly = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

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
  Widget build(BuildContext context) {
    final testsAsync = ref.watch(labsControllerProvider);
    final favourites = ref.watch(labFavouritesProvider);
    final isOffline = ref.watch(isOfflineProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Labs & Trends', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(labsControllerProvider.notifier).refresh(),
            tooltip: 'Refresh',
          ),
          const UserMenuButton(),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          if (isOffline)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.amber.shade100,
              child: Row(
                children: [
                  Icon(Icons.wifi_off, size: 16, color: Colors.amber.shade900),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Offline mode — showing cached lab results',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.amber.shade900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: testsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, color: Colors.red, size: 48),
              const SizedBox(height: 12),
              Text('Error loading labs: $err'),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.read(labsControllerProvider.notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (allTests) {
          if (allTests.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    Icon(Icons.biotech_outlined, size: 64, color: Colors.grey),
                    SizedBox(height: 16),
                    Text(
                      'No confirmed lab tests yet',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Confirm extractions on your uploaded reports to track values over time.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey),
                    ),
                  ],
                ),
              ),
            );
          }

          final filteredTests = allTests.where((t) {
            if (_filterAbnormalOnly && !t.isAbnormal) return false;
            if (_filter.isNotEmpty && !t.testName.toLowerCase().contains(_filter.toLowerCase())) {
              return false;
            }
            return true;
          }).toList();

          final favTests = allTests.where((t) {
            if (_filterAbnormalOnly && !t.isAbnormal) return false;
            return favourites.contains(t.testName);
          }).toList();

          return RefreshIndicator(
            onRefresh: () => ref.read(labsControllerProvider.notifier).refresh(),
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              children: [
                // Search bar
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search recorded tests...',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _filter.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear),
                            onPressed: () {
                              _searchController.clear();
                              setState(() => _filter = '');
                            },
                          )
                        : null,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  onChanged: (val) => setState(() => _filter = val),
                ),
                const SizedBox(height: 12),

                // Filter chips
                Row(
                  children: [
                    FilterChip(
                      label: Text('All (${allTests.length})'),
                      selected: !_filterAbnormalOnly,
                      onSelected: (_) => setState(() => _filterAbnormalOnly = false),
                    ),
                    const SizedBox(width: 8),
                    FilterChip(
                      avatar: Icon(
                        Icons.warning_amber_rounded,
                        size: 14,
                        color: _filterAbnormalOnly ? Colors.deepOrange.shade900 : Colors.deepOrange,
                      ),
                      label: Text('Abnormal (${allTests.where((t) => t.isAbnormal).length})'),
                      selected: _filterAbnormalOnly,
                      selectedColor: Colors.deepOrange.shade100,
                      onSelected: (val) => setState(() => _filterAbnormalOnly = val),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // FAVORITES SECTION
                if (favTests.isNotEmpty) ...[
                  Row(
                    children: const [
                      Icon(Icons.star, size: 18, color: Colors.amber),
                      SizedBox(width: 6),
                      Text(
                        'FAVORITE TRENDS',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: favTests.map((t) => _buildFavouriteCard(context, t)).toList(),
                  ),
                  const SizedBox(height: 20),
                ],

                // ALL TESTS SECTION
                const Text(
                  'ALL RECORDED TESTS',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.8,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 8),
                Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    side: BorderSide(color: Colors.grey.shade300),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: filteredTests.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (context, idx) {
                      final test = filteredTests[idx];
                      final isFav = favourites.contains(test.testName);
                      return ListTile(
                        title: Text(
                          test.testName,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text(
                          test.previousValue != null
                              ? 'Latest: ${test.latestDate ?? ''} • Prev: ${test.previousValue}'
                              : (test.latestDate != null
                                  ? 'Latest: ${test.latestDate} (${test.count} record${test.count > 1 ? 's' : ''})'
                                  : '${test.count} record${test.count > 1 ? 's' : ''}'),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (test.latestValue != null) ...[
                              Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        '${test.latestValue} ${test.latestUnit ?? ''}',
                                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                      ),
                                      if (test.deltaValue != null) ...[
                                        const SizedBox(width: 4),
                                        Icon(
                                          test.deltaValue! > 0
                                              ? Icons.arrow_upward
                                              : test.deltaValue! < 0
                                                  ? Icons.arrow_downward
                                                  : Icons.horizontal_rule,
                                          size: 11,
                                          color: test.deltaValue! > 0
                                              ? Colors.blue.shade700
                                              : test.deltaValue! < 0
                                                  ? Colors.deepOrange.shade700
                                                  : Colors.grey,
                                        ),
                                        Text(
                                          '${test.deltaValue! > 0 ? '+' : ''}${test.deltaValue!.toStringAsFixed(1)}',
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                            color: test.deltaValue! > 0
                                                ? Colors.blue.shade700
                                                : test.deltaValue! < 0
                                                    ? Colors.deepOrange.shade700
                                                    : Colors.grey,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                  if (test.latestFlag != null)
                                    Text(
                                      test.latestFlag!.toUpperCase(),
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: _getFlagColor(test.latestFlag),
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(width: 8),
                            ],
                            IconButton(
                              icon: Icon(
                                isFav ? Icons.star : Icons.star_border,
                                color: isFav ? Colors.amber : Colors.grey,
                              ),
                              onPressed: () =>
                                  ref.read(labFavouritesProvider.notifier).toggle(test.testName),
                              tooltip: isFav ? 'Unpin favorite' : 'Pin favorite',
                            ),
                            const Icon(Icons.chevron_right, color: Colors.grey),
                          ],
                        ),
                        onTap: () {
                          final enc = Uri.encodeComponent(test.testName);
                          context.go('/labs/$enc');
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          );
        },
      ),
          ),
        ],
      ),
    );
  }

  Widget _buildFavouriteCard(BuildContext context, LabTestSummary test) {
    return InkWell(
      onTap: () {
        final enc = Uri.encodeComponent(test.testName);
        context.go('/labs/$enc');
      },
      borderRadius: BorderRadius.circular(12),
      child: Container(
        width: 170,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey.shade300),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    test.testName,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (test.latestFlag != null)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: _getFlagColor(test.latestFlag).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      test.latestFlag!.toUpperCase(),
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                        color: _getFlagColor(test.latestFlag),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            if (test.latestValue != null) ...[
              Row(
                children: [
                  Text(
                    '${test.latestValue} ${test.latestUnit ?? ''}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  if (test.deltaValue != null) ...[
                    const SizedBox(width: 4),
                    Icon(
                      test.deltaValue! > 0
                          ? Icons.arrow_upward
                          : test.deltaValue! < 0
                              ? Icons.arrow_downward
                              : Icons.horizontal_rule,
                      size: 11,
                      color: test.deltaValue! > 0
                          ? Colors.blue.shade700
                          : test.deltaValue! < 0
                              ? Colors.deepOrange.shade700
                              : Colors.grey,
                    ),
                    Text(
                      '${test.deltaValue! > 0 ? '+' : ''}${test.deltaValue!.toStringAsFixed(1)}',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: test.deltaValue! > 0
                            ? Colors.blue.shade700
                            : test.deltaValue! < 0
                                ? Colors.deepOrange.shade700
                                : Colors.grey,
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 4),
              if (test.refLow != null && test.refHigh != null)
                Text(
                  'Ref: ${test.refLow}–${test.refHigh}',
                  style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                ),
            ] else ...[
              const Text('No data yet', style: TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ],
        ),
      ),
    );
  }
}

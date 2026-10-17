import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';

class ChartPoint {
  final DateTime date;
  final double value;
  final String? flag;
  final int documentId;
  final int pageNo;

  const ChartPoint({
    required this.date,
    required this.value,
    this.flag,
    required this.documentId,
    required this.pageNo,
  });

  factory ChartPoint.fromJson(Map<String, dynamic> json) {
    return ChartPoint(
      date: DateTime.parse(json['date'] as String),
      value: (json['value'] as num).toDouble(),
      flag: json['flag'] as String?,
      documentId: json['document_id'] as int? ?? 1,
      pageNo: json['page_no'] as int? ?? 1,
    );
  }
}

class LabChartData {
  final String testName;
  final List<ChartPoint> points;
  final double? refLow;
  final double? refHigh;
  final String? unit;

  const LabChartData({
    required this.testName,
    required this.points,
    this.refLow,
    this.refHigh,
    this.unit,
  });

  factory LabChartData.fromJson(Map<String, dynamic> json) {
    final rawPoints = json['points'] as List<dynamic>? ?? [];
    return LabChartData(
      testName: json['test_name'] as String? ?? '',
      points: rawPoints
          .map((p) => ChartPoint.fromJson(p as Map<String, dynamic>))
          .toList(),
      refLow: (json['ref_low'] as num?)?.toDouble(),
      refHigh: (json['ref_high'] as num?)?.toDouble(),
      unit: json['unit'] as String?,
    );
  }
}

final activeTimeRangeProvider = StateProvider.autoDispose<String>((ref) => 'ALL');

class LabChartController extends FamilyAsyncNotifier<LabChartData, String> {
  @override
  Future<LabChartData> build(String testName) async {
    final range = ref.watch(activeTimeRangeProvider);
    return _fetchChart(testName, range);
  }

  Future<LabChartData> _fetchChart(String testName, String range) async {
    final client = ref.read(apiClientProvider);
    final now = DateTime.now();
    DateTime? fromDate;

    switch (range) {
      case '3M':
        fromDate = DateTime(now.year, now.month - 3, now.day);
        break;
      case '6M':
        fromDate = DateTime(now.year, now.month - 6, now.day);
        break;
      case '1Y':
        fromDate = DateTime(now.year - 1, now.month, now.day);
        break;
      default:
        fromDate = null;
    }

    String path = '/charts/lab?test=${Uri.encodeComponent(testName)}';
    if (fromDate != null) {
      final fromStr =
          '${fromDate.year.toString().padLeft(4, '0')}-${fromDate.month.toString().padLeft(2, '0')}-${fromDate.day.toString().padLeft(2, '0')}';
      path += '&from=$fromStr';
    }

    final response = await client.dio.get(path);
    return LabChartData.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> reload() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _fetchChart(arg, ref.read(activeTimeRangeProvider)));
  }
}

final labChartProvider =
    AsyncNotifierProviderFamily<LabChartController, LabChartData, String>(
  LabChartController.new,
);

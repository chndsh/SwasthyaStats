class LabTestSummary {
  final String testName;
  final String? canonicalTestId;
  final int count;
  final double? latestValue;
  final String? latestUnit;
  final String? latestFlag;
  final String? latestDate;
  final double? refLow;
  final double? refHigh;

  const LabTestSummary({
    required this.testName,
    this.canonicalTestId,
    required this.count,
    this.latestValue,
    this.latestUnit,
    this.latestFlag,
    this.latestDate,
    this.refLow,
    this.refHigh,
  });

  factory LabTestSummary.fromJson(Map<String, dynamic> json) {
    return LabTestSummary(
      testName: json['test_name'] as String? ?? 'Unknown Test',
      canonicalTestId: json['canonical_test_id'] as String?,
      count: json['count'] as int? ?? 1,
      latestValue: (json['latest_value'] as num?)?.toDouble(),
      latestUnit: json['latest_unit'] as String?,
      latestFlag: json['latest_flag'] as String?,
      latestDate: json['latest_date'] as String?,
      refLow: (json['ref_low'] as num?)?.toDouble(),
      refHigh: (json['ref_high'] as num?)?.toDouble(),
    );
  }
}

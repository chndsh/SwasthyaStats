class ObservationModel {
  final int id;
  final String testName;
  final String? canonicalTestId;
  final double? valueNum;
  final String? valueText;
  final String? unit;
  final double? refLow;
  final double? refHigh;
  final String? flag;
  final String? collectedAt;
  final int pageNo;
  final List<int> sourceLineIds;
  final String status;
  final double? confidence;

  ObservationModel({
    required this.id,
    required this.testName,
    this.canonicalTestId,
    this.valueNum,
    this.valueText,
    this.unit,
    this.refLow,
    this.refHigh,
    this.flag,
    this.collectedAt,
    required this.pageNo,
    required this.sourceLineIds,
    required this.status,
    this.confidence,
  });

  factory ObservationModel.fromJson(Map<String, dynamic> json) {
    return ObservationModel(
      id: json['id'] as int,
      testName: json['test_name'] as String? ?? 'Unknown Test',
      canonicalTestId: json['canonical_test_id'] as String?,
      valueNum: (json['value_num'] as num?)?.toDouble(),
      valueText: json['value_text'] as String?,
      unit: json['unit'] as String?,
      refLow: (json['ref_low'] as num?)?.toDouble(),
      refHigh: (json['ref_high'] as num?)?.toDouble(),
      flag: json['flag'] as String?,
      collectedAt: json['collected_at'] as String?,
      pageNo: json['page_no'] as int? ?? 1,
      sourceLineIds: (json['source_line_ids'] as List<dynamic>?)
              ?.map((e) => e as int)
              .toList() ??
          [],
      status: json['status'] as String? ?? 'pending',
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }

  ObservationModel copyWith({
    String? testName,
    double? valueNum,
    String? valueText,
    String? unit,
    double? refLow,
    double? refHigh,
    String? flag,
  }) {
    return ObservationModel(
      id: id,
      testName: testName ?? this.testName,
      canonicalTestId: canonicalTestId,
      valueNum: valueNum ?? this.valueNum,
      valueText: valueText ?? this.valueText,
      unit: unit ?? this.unit,
      refLow: refLow ?? this.refLow,
      refHigh: refHigh ?? this.refHigh,
      flag: flag ?? this.flag,
      collectedAt: collectedAt,
      pageNo: pageNo,
      sourceLineIds: sourceLineIds,
      status: status,
      confidence: confidence,
    );
  }
}

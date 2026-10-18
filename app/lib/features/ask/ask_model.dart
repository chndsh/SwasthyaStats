class CitationRef {
  final String type; // 'obs' | 'doc'
  final int id;
  final int? page;

  CitationRef({
    required this.type,
    required this.id,
    this.page,
  });

  factory CitationRef.fromJson(Map<String, dynamic> json) {
    return CitationRef(
      type: json['type'] as String? ?? 'obs',
      id: json['id'] as int? ?? 0,
      page: json['page'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'id': id,
        if (page != null) 'page': page,
      };
}

class AskMessage {
  final String role; // 'user' | 'assistant'
  final String text;
  final List<CitationRef> citations;
  final DateTime timestamp;

  AskMessage({
    required this.role,
    required this.text,
    this.citations = const [],
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_door_mobile/main.dart';

void main() {
  testWidgets('SmartDoorApp renders live door camera and controls', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartDoorApp());
    expect(find.text('Smart Door Live Feed'), findsOneWidget);
    expect(find.textContaining('OUVRIR LA PORTE'), findsOneWidget);
    expect(find.text('Historique'), findsOneWidget);
    expect(find.text('Personnes'), findsOneWidget);
  });
}

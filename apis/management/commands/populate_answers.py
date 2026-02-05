# management/commands/populate_answers.py
from django.core.management.base import BaseCommand
from providers.models import ServiceQuestion, ServiceQuestionAnswer

class Command(BaseCommand):
    help = 'Populate answers for all service questions'

    def handle(self, *args, **kwargs):
        answers_data = [
            # Aadhaar Services (service_id: 1)
            # {
                # Add these to the answers_data list in the populate_answers.py management command

            {
                "question_id": 11,
                "answer_english": """Kisan Credit Card (KCC) Application:
KCC provides farmers with timely credit for agricultural needs at concessional interest rates.

ELIGIBILITY:
- Farmers (individual/joint owners)
- Tenant farmers, oral lessees, and sharecroppers
- Self Help Groups (SHGs) or Joint Liability Groups (JLGs) of farmers

DOCUMENTS REQUIRED:
- Aadhaar Card
- Land ownership documents/lease agreement
- PAN Card
- Two passport-size photographs
- Bank account statement (last 6 months)
- Income proof/land revenue records

APPLICATION PROCESS:
1. Visit any bank branch (preferably where you have Jan Dhan account)
2. Request KCC application form
3. Fill the form with personal, land, and crop details
4. Submit required documents
5. Bank will verify land records and creditworthiness
6. After approval, KCC will be issued within 15-30 days
7. Card valid for 5 years, renewable

CREDIT LIMIT:
- Based on cropping pattern and land holding
- Short term: Based on scale of finance for crops
- Long term: For allied activities (dairy, fishery, etc.)

INTEREST RATE:
- 7% per annum
- 4% interest subvention (making it 3%)
- Additional 3% incentive on prompt repayment (making it 0%)

BENEFITS:
- Hassle-free credit
- Insurance coverage (₹50,000 death/disability)
- Flexible repayment
- ATM withdrawal facility

Cost: Free card issuance""",
                "answer_hindi": """किसान क्रेडिट कार्ड (KCC) आवेदन:
KCC किसानों को रियायती ब्याज दरों पर कृषि आवश्यकताओं के लिए समय पर ऋण प्रदान करता है।

पात्रता:
- किसान (व्यक्तिगत/संयुक्त मालिक)
- काश्तकार किसान, मौखिक पट्टेदार और बटाईदार
- किसानों के स्वयं सहायता समूह (SHGs) या संयुक्त देयता समूह (JLGs)

आवश्यक दस्तावेज़:
- आधार कार्ड
- भूमि स्वामित्व दस्तावेज़/पट्टा समझौता
- पैन कार्ड
- दो पासपोर्ट आकार की तस्वीरें
- बैंक खाता विवरण (पिछले 6 महीने)
- आय प्रमाण/भूमि राजस्व रिकॉर्ड

आवेदन प्रक्रिया:
1. किसी भी बैंक शाखा में जाएं (अधिमानतः जहां आपका जन धन खाता है)
2. KCC आवेदन फॉर्म का अनुरोध करें
3. व्यक्तिगत, भूमि और फसल विवरण के साथ फॉर्म भरें
4. आवश्यक दस्तावेज़ जमा करें
5. बैंक भूमि रिकॉर्ड और साख की जांच करेगा
6. अनुमोदन के बाद, 15-30 दिनों में KCC जारी किया जाएगा
7. कार्ड 5 साल के लिए वैध, नवीकरणीय

ऋण सीमा:
- फसल पैटर्न और भूमि जोत पर आधारित
- अल्पकालिक: फसलों के लिए वित्त के पैमाने पर आधारित
- दीर्घकालिक: संबद्ध गतिविधियों के लिए (डेयरी, मत्स्य पालन, आदि)

ब्याज दर:
- 7% प्रति वर्ष
- 4% ब्याज सब्सिडी (इसे 3% बनाना)
- शीघ्र पुनर्भुगतान पर अतिरिक्त 3% प्रोत्साहन (इसे 0% बनाना)

लाभ:
- परेशानी मुक्त ऋण
- बीमा कवरेज (₹50,000 मृत्यु/विकलांगता)
- लचीली पुनर्भुगतान
- ATM निकासी सुविधा

लागत: मुफ्त कार्ड जारी करना"""
            }
            # },
        ]

        created_count = 0
        updated_count = 0

        for data in answers_data:
            question_id = data['question_id']
            
            try:
                question = ServiceQuestion.objects.get(id=question_id)
                answer, created = ServiceQuestionAnswer.objects.update_or_create(
                    question=question,
                    defaults={
                        'answer_english': data['answer_english'],
                        'answer_hindi': data['answer_hindi']
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created answer for Question ID {question_id}')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Updated answer for Question ID {question_id}')
                    )
                    
            except ServiceQuestion.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ Question ID {question_id} does not exist')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*50}\nSummary:\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total Processed: {created_count + updated_count}\n'
                f'{"="*50}'
            )
        )
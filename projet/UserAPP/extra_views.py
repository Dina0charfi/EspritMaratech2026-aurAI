
@csrf_exempt
def get_animation(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            word = data.get('word', '').lower().strip()
            
            # Construct path to animations
            animations_dir = settings.BASE_DIR / 'sign-avatar' / 'backend' / 'dataset_animations'
            json_path = animations_dir / f"{word}.json"
            
            if json_path.exists():
                with open(json_path, "r", encoding='utf-8') as f:
                    animation_data = json.load(f)
                return JsonResponse(animation_data, safe=False)
            else:
                return JsonResponse([], safe=False) # Return empty list if not found
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

from PIL import Image

from django import forms


class MaskForm(forms.ModelForm):
    def clean_image(self):
        value = self.cleaned_data['image']

        if value:
            image = Image.open(value.file)
            pixels = image.load()

            value.file.seek(0)

            try:
                assert len(pixels[0, 0]) >= 4
            except (AssertionError, TypeError):
                raise forms.ValidationError(
                    'The uploaded image does not contain alpha channel.'
                )

        return value

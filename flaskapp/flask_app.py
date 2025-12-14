from flask import render_template, Flask, request, flash, redirect, url_for
from flask_wtf import FlaskForm
from flask_wtf.recaptcha import RecaptchaField
from wtforms import SubmitField, FloatField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional
from flask_wtf.file import FileField, FileAllowed, FileRequired
from werkzeug.utils import secure_filename
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
import time

app = Flask(__name__)

app.config["SECRET_KEY"] = "top-secret"
app.config["UPLOAD_FOLDER"] = "./static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

app.config["RECAPTCHA_USE_SSL"] = False
app.config["RECAPTCHA_PUBLIC_KEY"] = "6Lf3ligsAAAAAFmaDNTaPwGhQAzcsi2NPwImeZgA"
app.config["RECAPTCHA_PRIVATE_KEY"] = "6Lf3ligsAAAAAHPcsUhid8N_W_Y6alfLlfF0zPfs"
app.config["RECAPTCHA_OPTIONS"] = {"theme": "white"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    """Проверяем расширение файла"""
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_color_histogram(image, title, filename):
    """Создает гистограмму распределения цветов изображения"""
    if image.mode != "RGB":
        image = image.convert("RGB")

    img_array = np.array(image)

    red = img_array[:, :, 0].flatten()
    green = img_array[:, :, 1].flatten()
    blue = img_array[:, :, 2].flatten()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"Гистограмма цветов - {title}", fontsize=16)

    colors = ["red", "green", "blue"]
    channels = [red, green, blue]
    channel_names = ["Красный", "Зеленый", "Синий"]

    for idx, (ax, color_channel, color, name) in enumerate(
        zip(axes, channels, colors, channel_names)
    ):
        ax.hist(
            color_channel,
            bins=64,
            range=(0, 256),
            color=color,
            alpha=0.7,
            edgecolor="black",
        )
        ax.set_title(f"{name} канал")
        ax.set_xlabel("Интенсивность")
        ax.set_ylabel("Частота")
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, 256])

    plt.tight_layout()

    hist_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    plt.savefig(hist_path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    return hist_path


@app.route("/")
def index():
    """Главная страница - перенаправление на форму изменения размера"""
    return redirect(url_for("resize_image"))


class ImageResizeForm(FlaskForm):
    """Форма для изменения размера изображения"""

    scale = FloatField(
        "Масштаб (0.1-10.0)",
        default=1.0,
        validators=[
            DataRequired(message="Укажите масштаб"),
            NumberRange(min=0.1, max=10.0, message="Масштаб от 0.1 до 10"),
        ],
    )

    width = IntegerField("Ширина (пиксели, необязательно)", validators=[Optional()])

    height = IntegerField("Высота (пиксели, необязательно)", validators=[Optional()])

    upload = FileField(
        "Загрузите изображение",
        validators=[
            FileRequired(message="Выберите файл изображения"),
            FileAllowed(["jpg", "png", "jpeg", "bmp", "gif"], "Только изображения!"),
        ],
    )

    recaptcha = RecaptchaField()

    submit = SubmitField("Изменить размер")


@app.route("/resize", methods=["GET", "POST"])
def resize_image():
    """Обработка формы изменения размера изображения"""
    form = ImageResizeForm()

    if request.method == "GET":
        form.scale.data = 1.0

    original_image = None
    resized_image = None
    original_hist = None
    resized_hist = None
    image_info = {}

    if form.validate_on_submit():
        try:
            file = form.upload.data

            if file and file.filename and allowed_file(file.filename):
                timestamp = str(int(time.time()))
                original_filename = (
                    f"original_{timestamp}_{secure_filename(file.filename)}"
                )
                original_path = os.path.join(
                    app.config["UPLOAD_FOLDER"], original_filename
                )

                file.save(original_path)

                with Image.open(original_path) as img:
                    image_info["original"] = {
                        "filename": file.filename,
                        "size": f"{img.size[0]}x{img.size[1]}",
                        "format": img.format or "Неизвестно",
                    }

                    hist_filename = f"hist_original_{timestamp}.png"
                    hist_path = create_color_histogram(
                        img.copy(), "Оригинал", hist_filename
                    )
                    original_hist = f"uploads/{hist_filename}"

                    if form.width.data and form.height.data:
                        new_size = (int(form.width.data), int(form.height.data))
                        scale_info = (
                            f"пользовательский {form.width.data}x{form.height.data}"
                        )
                    else:
                        scale = form.scale.data
                        new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
                        scale_info = f"{scale}x"

                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)

                    image_info["resized"] = {
                        "size": f"{resized_img.size[0]}x{resized_img.size[1]}",
                        "scale_used": scale_info,
                        "width": form.width.data,
                        "height": form.height.data,
                    }

                    resized_filename = (
                        f"resized_{timestamp}_{secure_filename(file.filename)}"
                    )
                    resized_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], resized_filename
                    )

                    if img.format:
                        resized_img.save(resized_path, format=img.format)
                    else:
                        resized_img.save(resized_path, format="JPEG")

                    resized_image = f"uploads/{resized_filename}"

                    resized_hist_filename = f"hist_resized_{timestamp}.png"
                    resized_hist_path = create_color_histogram(
                        resized_img, "Измененное", resized_hist_filename
                    )
                    resized_hist = f"uploads/{resized_hist_filename}"

                    original_image = f"uploads/{original_filename}"

                    if form.width.data and form.height.data:
                        flash(
                            f"✅ Изображение успешно обработано! Размер изменен с {img.size[0]}x{img.size[1]} на {resized_img.size[0]}x{resized_img.size[1]}. Капча пройдена.",
                            "success",
                        )
                    else:
                        flash(
                            f"✅ Изображение успешно обработано! Масштаб: {scale}x. Размер изменен с {img.size[0]}x{img.size[1]} на {resized_img.size[0]}x{resized_img.size[1]}. Капча пройдена.",
                            "success",
                        )

            else:
                flash("❌ Файл не выбран или имеет неверный формат", "danger")

        except Exception as e:
            print(f"Ошибка при обработке изображения: {str(e)}")
            flash(f"❌ Ошибка при обработке изображения: {str(e)}", "danger")

    elif request.method == "POST":
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                if field == "recaptcha":
                    error_messages.append(
                        "❌ Пожалуйста, подтвердите что вы не робот (капча)"
                    )
                elif field == "upload":
                    error_messages.append(f"❌ Ошибка загрузки файла: {error}")
                else:
                    field_label = (
                        getattr(form, field).label.text
                        if hasattr(form, field)
                        else field
                    )
                    error_messages.append(f"❌ {field_label}: {error}")

        if error_messages:
            flash("<br>".join(error_messages), "danger")
        else:
            flash("❌ Форма содержит ошибки. Пожалуйста, проверьте все поля.", "danger")

    return render_template(
        "resize.html",
        form=form,
        original_image=original_image,
        resized_image=resized_image,
        original_hist=original_hist,
        resized_hist=resized_hist,
        image_info=image_info,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8080)
else:
    application = app

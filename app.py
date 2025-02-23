import os
import matplotlib
matplotlib.use('Agg')  # Устанавливаем бэкенд Agg перед импортом pyplot
from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Создаем папку для загрузки файлов, если она не существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

ALLOWED_EXTENSIONS = {'csv', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_file(filepath):
    """Улучшенное чтение файла с определением формата и обработкой заголовков"""
    try:
        if filepath.endswith('.csv'):
            # Пробуем разные варианты чтения файла
            encodings = ['utf-8', 'windows-1251', 'latin1']
            separators = [',', ';', '\t', '|']
            
            for encoding in encodings:
                for sep in separators:
                    try:
                        # Сначала читаем несколько строк для анализа
                        preview_df = pd.read_csv(filepath, encoding=encoding, sep=sep, nrows=5)
                        
                        # Проверяем, есть ли в первой строке числа
                        first_row_numeric = pd.to_numeric(preview_df.iloc[0], errors='coerce').notna().any()
                        
                        # Если в первой строке числа, значит это данные, а не заголовки
                        header_row = None if first_row_numeric else 0
                        
                        # Читаем весь файл с определенными параметрами
                        df = pd.read_csv(filepath, encoding=encoding, sep=sep, header=header_row)
                        
                        # Если заголовков нет, создаем их
                        if header_row is None:
                            df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                            print(f"Заголовки созданы: {df.columns.tolist()}")
                        
                        # Проверяем качество чтения
                        if len(df.columns) > 1 and not all(col.startswith('Unnamed:') for col in df.columns):
                            print(f"Файл успешно прочитан с кодировкой {encoding} и разделителем '{sep}'")
                            # Вывод первых строк загруженного DataFrame
                            print("Первые строки загруженных данных:")
                            print(df.head())
                            return df
                        else:
                            print(f"Не удалось прочитать файл корректно с кодировкой {encoding} и разделителем '{sep}'")
                    except Exception as e:
                        print(f"Ошибка при чтении файла с кодировкой {encoding} и разделителем '{sep}': {str(e)}")
                        continue
            
            raise ValueError("Не удалось корректно прочитать CSV файл")
            
        elif filepath.endswith('.xlsx'):
            try:
                # Пробуем прочитать с разными параметрами
                try:
                    # Сначала пытаемся прочитать с автоопределением заголовков
                    df = pd.read_excel(filepath, engine='openpyxl')
                    print("Предварительный просмотр данных:")
                    print(df.head())
                    print("Типы данных:")
                    print(df.dtypes)
                    
                    # Проверяем, есть ли в первой строке числа
                    first_row_numeric = pd.to_numeric(df.iloc[0], errors='coerce').notna().any()
                    
                    if first_row_numeric:
                        # Если в первой строке числа, читаем файл заново без заголовков
                        df = pd.read_excel(filepath, engine='openpyxl', header=None)
                        df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                    else:
                        # Проверяем и исправляем заголовки
                        df.columns = [f'Column_{i+1}' if 'Unnamed' in str(col) else col 
                                    for i, col in enumerate(df.columns)]
                    
                    # Удаляем пустые строки и столбцы
                    df = df.dropna(how='all')
                    df = df.dropna(axis=1, how='all')
                    
                    print("Заголовки после обработки:", df.columns.tolist())
                    print("Размерность данных:", df.shape)
                    
                    # Вывод первых строк загруженного DataFrame
                    print("Первые строки загруженных данных:")
                    print(df.head())
                    
                    return df
                    
                except Exception as e:
                    print(f"Ошибка при чтении Excel файла: {str(e)}")
                    # Пробуем альтернативный метод чтения
                    df = pd.read_excel(filepath, engine='openpyxl', header=None)
                    df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                    return df
                    
            except Exception as e:
                print(f"Критическая ошибка при чтении Excel файла: {str(e)}")
                raise
            
    except Exception as e:
        print(f"Ошибка при чтении файла: {str(e)}")
        raise

def detect_and_convert_types(df):
    """Улучшенное определение и преобразование типов данных"""
    print("Начало определения типов данных")
    print("Исходные типы:", df.dtypes)
    
    for column in df.columns:
        # Пропускаем пустые столбцы
        if df[column].isna().all():
            print(f"Столбец {column} пропущен (все значения NA)")
            continue
        
        # Получаем непустые значения для анализа
        non_null_values = df[column].dropna()
        if len(non_null_values) == 0:
            print(f"Столбец {column} пропущен (нет непустых значений)")
            continue
        
        try:
            # Пробуем преобразовать в числа
            numeric_series = pd.to_numeric(non_null_values, errors='coerce')
            numeric_ratio = numeric_series.notna().mean()
            
            if numeric_ratio > 0.8:  # Если более 80% значений числовые
                # Проверяем, являются ли числа целыми
                if (numeric_series.dropna() % 1 == 0).all():
                    df[column] = pd.to_numeric(df[column], errors='coerce')
                    print(f"Столбец {column} преобразован в numeric (int)")
                else:
                    df[column] = pd.to_numeric(df[column], errors='coerce')
                    print(f"Столбец {column} преобразован в numeric (float)")
                continue
            
            # Если не числа, проверяем даты
            try:
                # Пробуем разные форматы дат
                date_formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']
                for date_format in date_formats:
                    try:
                        df[column] = pd.to_datetime(df[column], format=date_format, errors='coerce')
                        if not df[column].isna().all():
                            print(f"Столбец {column} преобразован в datetime с форматом {date_format}")
                            break
                    except:
                        continue
            except:
                # Если не даты, проверяем категориальные данные
                unique_ratio = len(non_null_values.unique()) / len(non_null_values)
                if unique_ratio < 0.2:  # Если уникальных значений менее 20%
                    df[column] = df[column].astype('category')
                    print(f"Столбец {column} преобразован в category")
                else:
                    df[column] = df[column].astype(str)
                    print(f"Столбец {column} оставлен как string")
        
        except Exception as e:
            print(f"Ошибка при обработке столбца {column}: {str(e)}")
            continue
    
    print("Итоговые типы:", df.dtypes)
    return df

def handle_missing_values(df):
    """Улучшенная обработка пропущенных значений"""
    print("Начало обработки пропущенных значений")
    print("Исходное количество пропущенных значений:")
    print(df.isnull().sum())
    
    # Сначала удаляем полностью пустые строки и столбцы
    df = df.dropna(how='all')
    df = df.dropna(axis=1, how='all')
    
    # Для числовых столбцов
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        missing_ratio = df[col].isna().mean()
        print(f"Обработка столбца {col} (пропущено {missing_ratio:.2%})")
        
        if missing_ratio > 0 and missing_ratio <= 0.3:
            # Используем интерполяцию для заполнения пропусков
            df[col] = df[col].interpolate(method='linear', limit_direction='both')
            print(f"  - Использована интерполяция")
        elif missing_ratio > 0.3 and missing_ratio <= 0.7:
            # Заполняем медианой
            median_value = df[col].median()
            df.loc[df[col].isna(), col] = median_value
            print(f"  - Заполнено медианой: {median_value}")
        elif missing_ratio > 0.7:
            print(f"  - Столбец будет удален")
            df = df.drop(columns=[col])
    
    # Для категориальных столбцов
    cat_cols = df.select_dtypes(include=['category', 'object']).columns
    for col in cat_cols:
        missing_ratio = df[col].isna().mean()
        if missing_ratio > 0:
            mode_value = df[col].mode().iloc[0] if not df[col].mode().empty else 'MISSING'
            df.loc[df[col].isna(), col] = mode_value
            print(f"Столбец {col}: заполнено значением '{mode_value}'")
    
    print("\nИтоговое количество пропущенных значений:")
    print(df.isnull().sum())
    
    return df

def handle_outliers(df, threshold=3):
    """Обработка выбросов методом z-score"""
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        # Пропускаем столбцы с пропущенными значениями
        if df[col].isna().any():
            continue
            
        # Вычисляем z-score
        z_scores = abs((df[col] - df[col].mean()) / df[col].std())
        # Заменяем выбросы на границы
        df.loc[z_scores > threshold, col] = df[col].mean()
    return df

def generate_extended_stats(df):
    """Расширенная генерация статистики с дополнительной информацией"""
    try:
        stats = {
            'basic': df.describe(include='all').round(2).to_html(classes='table table-striped'),
            'info': {
                'columns': df.columns.tolist(),
                'rows': len(df),
                'missing_values': df.isnull().sum().to_dict(),
                'dtypes': df.dtypes.astype(str).to_dict(),
                'memory_usage': round(df.memory_usage(deep=True).sum() / 1024**2, 2),  # в МБ
                'duplicates': df.duplicated().sum(),
                'unique_counts': df.nunique().to_dict(),
                'mean_values': df.mean(numeric_only=True).round(2).to_dict(),
            }
        }
        
        # Добавляем расширенную статистику для числовых данных
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            numeric_stats = {}
            for col in numeric_cols:
                numeric_stats[col] = {
                    'mean': round(df[col].mean(), 2),
                    'median': round(df[col].median(), 2),
                    'std': round(df[col].std(), 2),
                    'skew': round(df[col].skew(), 2),  # асимметрия
                    'kurtosis': round(df[col].kurtosis(), 2),  # эксцесс
                    'q1': round(df[col].quantile(0.25), 2),
                    'q3': round(df[col].quantile(0.75), 2),
                    'iqr': round(df[col].quantile(0.75) - df[col].quantile(0.25), 2),
                }
            stats['numeric_stats'] = numeric_stats
        
        # Добавляем корреляцию для числовых данных
        if len(numeric_cols) > 1:
            correlation = df[numeric_cols].corr().round(2)
            # Находим сильные корреляции
            strong_correlations = []
            for i in range(len(correlation.columns)):
                for j in range(i+1, len(correlation.columns)):
                    corr_value = correlation.iloc[i, j]
                    if abs(corr_value) > 0.7:  # Порог для сильной корреляции
                        strong_correlations.append({
                            'col1': correlation.columns[i],
                            'col2': correlation.columns[j],
                            'correlation': corr_value
                        })
            stats['correlation'] = correlation.to_html(classes='table table-striped')
            stats['strong_correlations'] = strong_correlations
        
        # Добавляем статистику по категориальным данным
        cat_cols = df.select_dtypes(include=['category', 'object']).columns
        if len(cat_cols) > 0:
            cat_stats = {}
            for col in cat_cols:
                value_counts = df[col].value_counts()
                cat_stats[col] = {
                    'unique_values': df[col].nunique(),
                    'top_values': value_counts.head(5).to_dict(),
                    'top_percentages': (value_counts.head(5) / len(df) * 100).round(2).to_dict()
                }
            stats['categorical'] = cat_stats
        
        # Анализ выбросов
        outliers_info = {}
        for col in numeric_cols:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]
            outliers_info[col] = {
                'count': len(outliers),
                'percentage': round(len(outliers) / len(df) * 100, 2),
                'min_outlier': round(outliers.min(), 2) if not outliers.empty else None,
                'max_outlier': round(outliers.max(), 2) if not outliers.empty else None,
                'bounds': {
                    'lower': round(lower_bound, 2),
                    'upper': round(upper_bound, 2)
                }
            }
        stats['outliers'] = outliers_info
        
        return stats
    except Exception as e:
        print(f"Ошибка при генерации статистики: {str(e)}")
        return {'basic': '', 'info': {}, 'correlation': None, 'categorical': None, 'outliers': {}}

def create_visualization(df, plot_type, x_column, y_column=None):
    """Улучшенное создание визуализации с обработкой ошибок"""
    try:
        plt.figure(figsize=(12, 8))
        plt.clf()
        
        if plot_type == 'histogram':
            if df[x_column].dtype in ['int64', 'float64']:
                # Добавляем кривую плотности
                sns.histplot(data=df, x=x_column, bins=30, kde=True)
                plt.title(f'Распределение {x_column}')
                # Добавляем среднее и медиану
                plt.axvline(df[x_column].mean(), color='red', linestyle='--', label='Среднее')
                plt.axvline(df[x_column].median(), color='green', linestyle='--', label='Медиана')
                plt.legend()
            else:
                raise ValueError("Для гистограммы требуются числовые данные")
        
        elif plot_type == 'boxplot':
            if df[x_column].dtype in ['int64', 'float64']:
                sns.boxplot(data=df, y=x_column)
                plt.title(f'Ящик с усами для {x_column}')
                # Добавляем точки выбросов
                sns.stripplot(data=df, y=x_column, color='red', alpha=0.3)
            else:
                raise ValueError("Для ящика с усами требуются числовые данные")
        
        elif plot_type == 'scatter' and y_column:
            if df[x_column].dtype in ['int64', 'float64'] and df[y_column].dtype in ['int64', 'float64']:
                # Добавляем линию регрессии
                sns.regplot(data=df, x=x_column, y=y_column, scatter_kws={'alpha':0.5})
                plt.title(f'Диаграмма рассеяния {x_column} vs {y_column}')
                # Добавляем коэффициент корреляции
                corr = df[x_column].corr(df[y_column])
                plt.text(0.05, 0.95, f'Корреляция: {corr:.2f}', 
                        transform=plt.gca().transAxes, 
                        bbox=dict(facecolor='white', alpha=0.8))
            else:
                raise ValueError("Для диаграммы рассеяния требуются числовые данные")
        
        elif plot_type == 'bar':
            value_counts = df[x_column].value_counts().head(10)
            plt.figure(figsize=(12, 6))
            ax = sns.barplot(x=value_counts.index, y=value_counts.values)
            plt.title(f'Top 10 значений в {x_column}')
            plt.xticks(rotation=45, ha='right')
            # Добавляем подписи значений
            for i, v in enumerate(value_counts.values):
                ax.text(i, v, str(v), ha='center', va='bottom')
        
        plt.tight_layout()
        img_path = os.path.join('static', 'plot.png')
        plt.savefig(img_path, dpi=300, bbox_inches='tight')
        plt.close()
        return 'plot.png'
    except Exception as e:
        print(f"Ошибка при создании визуализации: {str(e)}")
        return None

def preprocess_data(df):
    """Комплексная обработка данных"""
    # Определение и преобразование типов
    df = detect_and_convert_types(df)
    
    # Обработка пропущенных значений
    df = handle_missing_values(df)
    
    # Обработка выбросов
    df = handle_outliers(df)
    
    # Удаление дубликатов
    df.drop_duplicates(inplace=True)
    
    return df

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'Файл не выбран'
        
        file = request.files['file']
        if file.filename == '':
            return 'Файл не выбран'
        
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Читаем и обрабатываем файл
                df = read_file(filepath)
                df = preprocess_data(df)
                
                # Получаем расширенную статистику
                stats = generate_extended_stats(df)
                if stats is None:
                    return 'Ошибка при генерации статистики'
                
                # Создаем начальный график
                numeric_cols = df.select_dtypes(include=['number']).columns
                plot_filename = None
                if len(numeric_cols) > 0:
                    plot_filename = create_visualization(df, 'histogram', numeric_cols[0])
                
                return render_template('report.html',
                                     stats=stats,  # Передаем весь объект stats
                                     basic_stats=stats['basic'],
                                     info=stats['info'],
                                     correlation=stats.get('correlation'),
                                     categorical_stats=stats.get('categorical'),
                                     plot=plot_filename,
                                     columns=df.columns.tolist(),
                                     numeric_columns=numeric_cols.tolist(),
                                     filename=filename)
            except Exception as e:
                print(f"Ошибка при обработке файла: {str(e)}")  # Добавляем вывод ошибки в консоль
                return f'Ошибка при обработке файла: {str(e)}'
    
    return render_template('upload.html')

@app.route('/update_plot', methods=['POST'])
def update_plot():
    try:
        data = request.json
        filename = data['filename']
        plot_type = data['plot_type']
        x_column = data['x_column']
        y_column = data.get('y_column')
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = read_file(filepath)
        
        plot_filename = create_visualization(df, plot_type, x_column, y_column)
        if plot_filename is None:
            return jsonify({'error': 'Ошибка при создании графика'}), 400
        
        return jsonify({'plot': plot_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download_pdf/<filename>')
def download_pdf(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = read_file(filepath)
        stats = generate_extended_stats(df)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        )
        elements.append(Paragraph(f"Отчет по файлу: {filename}", title_style))
        elements.append(Spacer(1, 12))
        
        # Основная информация
        elements.append(Paragraph("Основная информация:", styles['Heading2']))
        info_text = [
            f"Количество строк: {stats['info']['rows']}",
            f"Количество столбцов: {len(stats['info']['columns'])}",
            "Типы данных:"
        ]
        for col, dtype in stats['info']['dtypes'].items():
            info_text.append(f"- {col}: {dtype}")
        
        for line in info_text:
            elements.append(Paragraph(line, styles['Normal']))
            elements.append(Spacer(1, 6))
        
        # Добавляем график
        if os.path.exists(os.path.join('static', 'plot.png')):
            elements.append(Paragraph("Визуализация:", styles['Heading2']))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph('<img src="static/plot.png" width="500" height="300"/>', styles['Normal']))
        
        # Генерируем PDF
        doc.build(elements)
        buffer.seek(0)
        return send_file(buffer,
                        download_name='report.pdf',
                        as_attachment=True,
                        mimetype='application/pdf')
    except Exception as e:
        return f'Ошибка при создании PDF: {str(e)}'

if __name__ == '__main__':
    app.run(debug=True) 
    app.run(debug=True) 
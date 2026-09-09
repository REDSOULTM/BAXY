"""Recover reviewed historical explanations instead of their corrupted acknowledgements."""
from pathlib import Path
import copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime
OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot4-data'
PARENT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot3-data'
HISTORY_SOURCE=ROOT.parent/'Probando Gemma 4/dataset_finetune/curated/train_v3.jsonl'
assert not OUT.exists();OUT.mkdir()
class Captured(Exception):pass
class Recorder(LlmRuntime):
    def __init__(self):self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf';self.payload=None
    def _post(self,payload):self.payload=copy.deepcopy(payload);raise Captured()
history=[{'role':'user','content':'What is a triangle?'},{'role':'assistant','content':'A triangle has three straight sides.'},
         {'role':'user','content':'¿Y un cuadrado?'},{'role':'assistant','content':'Tiene cuatro lados iguales y cuatro ángulos rectos.'}]
def payload(question,lang,prior=None):
    recorder=Recorder()
    try:recorder.chat(question,history=prior,conversation_kind='knowledge',response_language=lang)
    except Captured:pass
    assert recorder.payload
    return recorder.payload
# Each tuple was individually reviewed against the selected original explanation.
# Translations and narrowly qualified wording are authored here, not historical model outputs.
reviewed=[
 (568,'api','¿Qué es una API?','What is an API?',
  'Una API es una interfaz para que los programas se comuniquen. Define cómo solicitar datos o funciones y cómo recibir la respuesta.',
  'An API is an interface that lets programs communicate. It defines how to request data or functions and receive a response.',
  'Una API permite que los programas se comuniquen. It defines how to request data or functions and receive a response.'),
 (1306,'closure','¿Qué es una closure en JavaScript?',"What is a closure in JavaScript?",
  'Una closure combina una función con acceso a las variables del entorno donde se creó. Puede conservar ese acceso aunque la función externa haya terminado.',
  'A closure combines a function with access to variables from the environment where it was created. That access can remain after the outer function has returned.',
  'Una closure combina una función con acceso a las variables del entorno donde se creó. That access can remain after the outer function has returned.'),
 (1312,'mvc','¿Qué es MVC?','What is MVC?',
  'MVC separa una aplicación en modelo, vista y controlador. El modelo gestiona los datos, la vista los presenta y el controlador maneja la interacción.',
  'MVC separates an application into model, view and controller. The model manages data, the view presents it and the controller handles interaction.',
  'MVC separa una aplicación en modelo, vista y controlador. The model manages data, the view presents it and the controller handles interaction.'),
 (1313,'tdd','¿Qué es TDD?','What is TDD?',
  'TDD es desarrollar guiándose por pruebas. Escribes una prueba que falla, implementas lo necesario para que pase y luego refactorizas conservando las pruebas verdes.',
  'TDD means test-driven development. You write a failing test, implement enough code to pass it, then refactor while keeping the tests passing.',
  'TDD consiste en desarrollar guiándose por pruebas. You write a failing test, make it pass, then refactor while keeping the tests passing.'),
 (58,'markdown','¿Qué es un archivo Markdown?','What is a Markdown file?',
  'Un archivo Markdown contiene texto plano con marcas para indicar formato. Por ejemplo, puedes marcar títulos o listas sin usar un editor de texto enriquecido.',
  'A Markdown file contains plain text with marks that indicate formatting. For example, you can mark headings or lists without a rich text editor.',
  'Un archivo Markdown contiene texto plano con marcas para indicar formato. For example, you can mark headings or lists without a rich text editor.'),
 (66,'environment','¿Qué es una variable de entorno?','What is an environment variable?',
  'Una variable de entorno es un valor con nombre que un programa recibe en su entorno de ejecución. Se suele usar para comunicar configuración, como una ruta.',
  'An environment variable is a named value available to a program in its execution environment. It is often used to pass configuration, such as a path.',
  'Una variable de entorno es un valor con nombre disponible para un programa. It is often used to pass configuration, such as a path.'),
 (106,'requests','¿Qué es Requests en Python?','What is Requests in Python?',
  'Requests es una biblioteca de Python para hacer peticiones HTTP. Simplifica tareas como enviar una petición y leer la respuesta del servidor.',
  'Requests is a Python library for making HTTP requests. It simplifies tasks such as sending a request and reading the server response.',
  'Requests es una biblioteca de Python para hacer peticiones HTTP. It simplifies sending requests and reading server responses.'),
 (1151,'objects','¿Qué es la programación orientada a objetos?','What is object-oriented programming?',
  'La programación orientada a objetos organiza datos y comportamiento en objetos. Cada objeto reúne un estado y métodos que trabajan con él.',
  'Object-oriented programming organizes data and behavior into objects. An object brings together state and methods that work with it.',
  'La programación orientada a objetos organiza datos y comportamiento en objetos. Each object brings together state and methods that work with it.'),
 (1150,'python','¿Qué es Python?','What is Python?',
  'Python es un lenguaje de programación de alto nivel. Se utiliza, entre otras cosas, para automatizar tareas, desarrollar aplicaciones y analizar datos.',
  'Python is a high-level programming language. It is used for tasks such as automation, application development and data analysis.',
  'Python es un lenguaje de programación de alto nivel. It is used for tasks such as automation, application development and data analysis.'),
 (4594,'sql','¿Qué es SQL?','What is SQL?',
  'SQL es un lenguaje para trabajar con bases de datos relacionales. Permite consultar datos y, según la sentencia y los permisos, crearlos, modificarlos o eliminarlos.',
  'SQL is a language for working with relational databases. It supports queries and, depending on the statement and permissions, creating, modifying or deleting data.',
  'SQL es un lenguaje para trabajar con bases de datos relacionales. It supports querying data and, with the appropriate statements and permissions, changing it.'),
 (4617,'statistics','¿En qué se diferencian la estadística descriptiva y la inferencial?','How do descriptive and inferential statistics differ?',
  'La estadística descriptiva resume los datos observados. La inferencial usa una muestra para sacar conclusiones sobre una población, teniendo en cuenta la incertidumbre.',
  'Descriptive statistics summarize the observed data. Inferential statistics use a sample to draw conclusions about a population while accounting for uncertainty.',
  'La estadística descriptiva resume los datos observados. Inferential statistics use a sample to draw conclusions about a population while accounting for uncertainty.'),
 (4505,'frank','¿Qué significa frank en inglés?','What does frank mean?',
  'Frank puede describir a alguien franco, sincero y directo al hablar. También puede ser un nombre propio; el sentido depende del contexto.',
  'Frank can describe someone who is candid, honest and direct in speech. It can also be a given name, so the meaning depends on context.',
  'Frank puede describir a alguien franco, sincero y directo al hablar. It can also be a given name, so the meaning depends on context.'),
 (4438,'lie-lay','¿Cuál es la diferencia entre lie y lay en inglés?','What is the difference between lie and lay?',
  'Al hablar de posición, lie significa estar o ponerse recostado, mientras que lay significa colocar algo. Lay necesita un objeto: colocas algo; lie no lo necesita en ese sentido.',
  'When describing position, lie means to recline, while lay means to put something down. Lay takes an object, whereas lie does not in this sense.',
  'Al hablar de posición, lie significa recostarse y lay significa colocar algo. Lay takes an object, whereas lie does not in this sense.'),
 (2815,'latency','¿Qué es la latencia?','What is latency?',
  'La latencia es el tiempo de espera entre un evento y la respuesta que se mide. Por ejemplo, puede medirse desde que envías una petición hasta que recibes la respuesta.',
  'Latency is the delay between an event and the response being measured. For example, it may be measured from sending a request to receiving its response.',
  'La latencia es el tiempo de espera entre un evento y la respuesta que se mide. For example, it may be measured from sending a request to receiving its response.'),
 (1760,'percentile','¿Qué es el p95 de latencia?','What does p95 latency mean?',
  'El p95 es el percentil 95 de las latencias medidas. Aproximadamente el 95% de las observaciones quedan en ese valor o por debajo; no es el promedio.',
  'P95 is the 95th percentile of measured latencies. About 95% of observations are at or below that value; it is not the average.',
  'El p95 es el percentil 95 de las latencias medidas. About 95% of observations are at or below that value; it is not the average.'),
 (53,'resistor','¿Qué es una resistencia eléctrica como componente?','What is a resistor?',
  'Una resistencia es un componente que se opone al paso de corriente eléctrica. Su resistencia se mide en ohmios y puede usarse para limitar corriente.',
  'A resistor is a component that opposes the flow of electric current. Its resistance is measured in ohms, and it can be used to limit current.',
  'Una resistencia es un componente que se opone al paso de corriente eléctrica. Its resistance is measured in ohms, and it can be used to limit current.'),
 (64,'idempotent','¿Qué significa que una operación sea idempotente?','What does idempotent mean for an operation?',
  'Una operación es idempotente si repetirla tiene el mismo efecto previsto que ejecutarla una sola vez. Por ejemplo, fijar un valor ya fijado no lo incrementa con cada repetición.',
  'An operation is idempotent if repeating it has the same intended effect as doing it once. For example, assigning an already assigned value does not increase it on each repetition.',
  'Una operación es idempotente si repetirla tiene el mismo efecto previsto que ejecutarla una sola vez. Assigning an already assigned value, for example, does not increase it on each repetition.'),
 (62,'regression','¿Qué es una prueba de regresión?','What is a regression test?',
  'Una prueba de regresión comprueba que un cambio no haya roto un comportamiento que debía seguir funcionando. Puede conservar un caso que antes falló para detectar si ese problema reaparece.',
  'A regression test checks that a change has not broken behavior that should still work. It can preserve a previously failing case to detect whether the same problem returns.',
  'Una prueba de regresión comprueba que un cambio no rompa un comportamiento que debía seguir funcionando. It can preserve a previously failing case to detect whether that problem returns.'),
 (1748,'technical-debt','¿Qué es la deuda técnica?','What is technical debt?',
  'La deuda técnica es trabajo futuro que queda pendiente por decisiones o limitaciones del diseño y del código. Puede permitir avanzar antes, pero añade costes de mantenimiento o cambios posteriores.',
  'Technical debt is future work left by decisions or limitations in a design or codebase. It may allow earlier progress but adds maintenance costs or later changes.',
  'La deuda técnica es trabajo futuro que queda pendiente por decisiones o limitaciones del diseño y del código. It may allow earlier progress but adds maintenance costs or later changes.'),
 (1143,'dna','¿Qué es el ADN?','What is DNA?',
  'El ADN es una molécula que almacena información genética. Su secuencia contiene instrucciones que las células utilizan para desarrollarse y funcionar.',
  'DNA is a molecule that stores genetic information. Its sequence carries instructions that cells use to develop and function.',
  'El ADN es una molécula que almacena información genética. Its sequence carries instructions that cells use to develop and function.'),
]
selected={r[0] for r in reviewed};originals={};replaced=[]
with HISTORY_SOURCE.open(encoding='utf-8') as f:
    for n,line in enumerate(f,1):
        row=json.loads(line)
        if n in selected:originals[n]=row
        if row.get('lang') in ['es','en'] and not row.get('correct_tools') and not row.get('prev_text') and row.get('category') in ['info','conversacion'] and row.get('reply_is_template') and row.get('correct_reply_style')!=row.get('final_reply'):
            replaced.append({'line':n,'request':row.get('user_text'),'originalExplanation':row.get('correct_reply_style'),'trainingTarget':row.get('final_reply')})
assert len(originals)==len(reviewed)==20
train=[json.loads(x) for x in (PARENT/'TRAIN.jsonl').read_text(encoding='utf-8').splitlines()]
holdout=[json.loads(x) for x in (PARENT/'HOLDOUT.jsonl').read_text(encoding='utf-8').splitlines()]
review=[]
for index,(line,topic,qes,qen,aes,aen,amixed) in enumerate(reviewed):
    original=originals[line];assert not original['correct_tools'] and original['correct_reply_style']
    review.append({'line':line,'topic':topic,'original':original,'decision':'Use reviewed conceptual content from correct_reply_style, never blindly final_reply. Targets below are reviewed adaptations and translations.',
                   'adaptedAnswers':{'es':aes,'en':aen,'mixed':amixed}})
    qm=(qes+' Answer in Spanglish.') if index%2==0 else (qen+' Explícalo en spanglish.')
    for lang,question,answer in zip(['es','en','mixed'],[qes,qen,qm],[aes,aen,amixed]):
        if index%3==0:question+= ' Use two sentences.' if lang=='en' else ' Usa dos oraciones.'
        prior=history if index%2 else None
        train.append({'id':f'inherited-{topic}-{lang}','language':lang,'request':question,'answer':answer,
                      'payload':payload(question,lang,prior),'history':prior,'synthetic':True,'sourceLine':line,
                      'sourceField':'correct_reply_style','sourcePath':str(HISTORY_SOURCE),'review':'assistant-reviewed adaptation/translation; not an observed current PC state'})
reserved=[
 ('synonym',['¿Qué es un sinónimo?','What is a synonym?','What is a synonym? Explícalo en spanglish.'], 'Word or expression with same or similar meaning in some context; not identical spelling or opposite meaning.'),
 ('balloon',['¿Por qué un globo se expande al meterle aire?','Why does a balloon expand when air is added?','Why does a balloon expand with air? Responde en spanglish.'], 'Added gas exerts pressure on the flexible wall, stretching it; not because air lacks mass or because air becomes solid.'),
 ('ram-storage',['¿Qué diferencia hay entre RAM y almacenamiento?','How do RAM and storage differ?','How do RAM and storage differ? Responde en spanglish.'], 'RAM is working memory, normally volatile; storage retains data without power. Do not claim current PC capacity or inspect it.'),
 ('sieve',['¿Cómo separa materiales un colador?','How does a sieve separate materials?','How does a sieve separate materials? Responde en spanglish.'], 'Openings let smaller particles or liquid through while retaining larger pieces; no claim it removes all dissolved substances.'),
]
for topic,questions,criteria in reserved:
    for lang,question in zip(['es','en','mixed'],questions):
        holdout.append({'id':f'breadth-heldout-{topic}-{lang}','language':lang,'request':question,
                        'payload':payload(question,lang,history),'history':history,'synthetic':True,
                        'criteria':criteria+' Useful, factual and in requested language; no complete repeated translation. No fixed sentence count requested.'})
assert len(train)==192 and len(holdout)==42
assert not ({r['request'] for r in train}&{r['request'] for r in holdout})
for name,rows in [('TRAIN.jsonl',train),('HOLDOUT.jsonl',holdout),('HERITAGE_REVIEW.jsonl',review),('HISTORICAL_REPLACEMENTS.jsonl',replaced)]:
    (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
with HISTORY_SOURCE.open('rb') as f:source_sha=hashlib.file_digest(f,'sha256').hexdigest()
manifest={'kind':'reviewed-heritage-knowledge-pilot-not-acceptance','trainCount':192,'holdoutCount':42,
 'hypothesis':'Prior tiny-topic tuning improves format but alters unseen facts. Add 20 individually reviewed inherited knowledge concepts in three languages to preserve broader factual behavior; do not train on consumed development questions.',
 'same':'Base weights, LoRA profile, response-only loss, two epochs and learning rate unchanged. All 132 prior examples retained; 60 reviewed additions.',
 'source':str(HISTORY_SOURCE),'sourceSha256':source_sha,'selectedLines':sorted(selected),'replacementsObserved':len(replaced),
 'historicalCause':'Probando Gemma 4/dataset_finetune/scripts/build_v3.py:795-798 replaces no-tool reply_is_template explanations with ack, even when an actual explanatory target exists.',
 'primaryCrossChecks':['https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures','https://requests.readthedocs.io/en/latest/','https://docs.python.org/3/tutorial/classes.html','https://www.genome.gov/genetics-glossary/Deoxyribonucleic-Acid-DNA'],
 'files':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['TRAIN.jsonl','HOLDOUT.jsonl','HERITAGE_REVIEW.jsonl','HISTORICAL_REPLACEMENTS.jsonl']}}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
runner=(ROOT/'scratchpad/c03-train-lora-pilot.py').read_text(encoding='utf-8').replace('48-example','192-example').replace('astra-lora-pilot-training','astra-lora-pilot4-training').replace('c03-pilot-lora-v1','c03-pilot-lora-v4').replace('astra-lora-pilot-data','astra-lora-pilot4-data')
target=ROOT/'scratchpad/c03-train-lora-pilot4.py';assert not target.exists();target.write_text(runner,encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))

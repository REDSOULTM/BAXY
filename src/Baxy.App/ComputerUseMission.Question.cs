using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

// A goal that carries the person's question: what is read on screen to answer it.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// Lectura-ruta (r9 v3-61 «en seguridad de windows decime cuándo fue el último examen de virus», reached with 0
    /// steps on the start page, where the datum is not): a goal that carries a question («; y responder: ») is not
    /// reached by its check holding on the window's identity alone (a title or a process term) while the sub-goal did
    /// nothing but open the application; the question's datum may live on another page. The model decides then: it
    /// cites the answer on screen (done) or takes the step to the page that shows it. After an act of the sub-goal that
    /// took effect the check stands as usual. Review of the branch (finding 3): an act that failed (ok false, among them
    /// the no-progress refusal) or changed nothing on screen (a click again on the page already shown) moved nowhere,
    /// so it is no such act; and the window's header, like its title, names the window, never a place in it.
    /// </summary>
    internal static bool QuestionUnlookedFor(string? goal, string? satisfiedBy, IEnumerable<JsonNode?> subgoalSteps)
    {
        if (goal is null || !goal.Contains(OperationFloor.QuestionMark, StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(satisfiedBy))
        {
            return false;
        }

        // Every atom of the term that held names the window itself (title:, header:, process:; a resemblance mark adds
        // nothing), never a place inside it.
        bool identityOnly = satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .All(atom => AtomKindOf(atom) is "title" or "header" or "process" or SimilarAtom);
        return identityOnly && !subgoalSteps.OfType<JsonObject>().Any(step =>
            (string?)step["operation"] != "app.open" && (bool?)step["ok"] == true && (bool?)step["changed"] == true);
    }

    /// <summary>
    /// Pasada r15b C1 (v3-43 «decime qué plan está activo», closed by «stepDone:input.visible.click:opciones de energia»
    /// on the page still loading, its screen values only the «Cargando» bar; v3-18 closed by «title:paisaje&amp;stepDone:
    /// file.open»): a goal that carries a question asks for a value, and a term that only names the window or the act
    /// done (title, header, process, stepDone, a resemblance mark) reads none. It holds only when the look it held on
    /// is loaded (no loading indicator, <see cref="ShowsLoading"/>) and is not empty of data: some value or chosen item
    /// of a control other than a loading indicator, or some line of text read on it (what the final quotes,
    /// ScreenExcerpt). Review of fable/cu-v3-carga-preguntas (finding 3): that is all it asks. It catches a look still
    /// loading or empty; it does not judge that the datum shown answers the question (a navigation item chosen counts
    /// as much as the plan chosen: an answer rarely shares a word with its question, «Equilibrado» for «qué plan»,
    /// «1920 x 1080» for «qué dimensiones», so relatedness would send every question back to the model).
    /// Without one the mission goes on with the model: it cites the answer on screen (done) or takes the step that
    /// shows it. A term that reads in the window (control:, text:, page:, value:…) and the model's own citation stand.
    /// Pasada r18 (v3-46, v3-61): what the sub-goal's own acts put there is no datum of the window
    /// (<paramref name="subgoalSteps"/>): an item shown chosen, on or checked that a verified click of the sub-goal pressed
    /// by its name (the navigation entry the act chose, read before the page beside it was drawn, or chosen by mistake),
    /// and a field's value that only repeats what the sub-goal typed (<see cref="ComputerUseSuccessCheck.EchoesTyping"/>).
    /// An item chosen before and left untouched (the plan «Equilibrado» while the act pressed «Opciones de energía») and
    /// any other value of the page stand.
    /// </summary>
    internal static bool QuestionDatumUnread(
        string? goal, string? satisfiedBy, JsonObject view, JsonArray? subgoalSteps = null,
        IReadOnlyCollection<string>? appeared = null, string? check = null)
    {
        if (!CarriesQuestion(goal) || string.IsNullOrWhiteSpace(satisfiedBy) || satisfiedBy == "model_evidence")
        {
            return false;
        }

        // Ronda 24 (v3-39, «open settings and tell me which profile is the default» closed by control:configuracion:current):
        // a control, a page or a mark that names the goal's own place (the X of «ir a X», or a name the check gives it by
        // a title: atom) is the window's identity like a title, and reads no datum.
        HashSet<string> placeNames = GoalPlaceNames(goal, check);
        bool readsNothing = satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .All(atom => AtomKindOf(atom) is "title" or "header" or "process" or "stepdone" or SimilarAtom
                || (AtomKindOf(atom) is "control" or "page" or "mark" && placeNames.Contains(AtomPlaceName(atom))));
        if (!readsNothing)
        {
            return false;
        }

        if (ShowsLoading(view))
        {
            return true;
        }

        JsonObject excerpt = ScreenExcerpt(view, goal, appeared);
        JsonArray acts = subgoalSteps ?? [];
        bool valued = excerpt["values"] is JsonArray values && values.OfType<JsonObject>().Any(item =>
            !OperationFloor.NamesLoading(ComputerUseSuccessCheck.Fold((string?)item["name"]))
            && !(item["state"] is not null && item["value"] is null && ComputerUseSuccessCheck.ClickedByName((string?)item["name"], acts))
            && !(item["value"] is not null && item["state"] is null && ComputerUseSuccessCheck.EchoesTyping((string?)item["value"], acts)));
        return !valued && excerpt["lines"] is not JsonArray { Count: > 0 };
    }

    // Ronda 24: the folded names of a question goal's place: the X of «ir a X» said before the question, and the names
    // of the planned check's title: atoms (the planner's own names for it in the window's languages).
    private static HashSet<string> GoalPlaceNames(string? goal, string? check)
    {
        var names = new HashSet<string>(StringComparer.Ordinal);
        if (goal is null)
        {
            return names;
        }

        int at = goal.IndexOf(OperationFloor.QuestionMark, StringComparison.Ordinal);
        string place = ComputerUseSuccessCheck.Fold(OperationFloor.PlaceAsked(at >= 0 ? goal[..at] : goal)).Trim();
        if (place.Length > 0)
        {
            names.Add(place);
        }

        foreach (string atom in (check ?? string.Empty).Split(['|', '&'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (AtomKindOf(atom) == "title" && AtomPlaceName(atom) is { Length: > 0 } name)
            {
                names.Add(name);
            }
        }

        return names;
    }

    // The folded name an atom reads: what follows its kind, without a control's trailing state («control:x:current»).
    private static string AtomPlaceName(string atom)
    {
        string rest = atom[(atom.IndexOf(':', StringComparison.Ordinal) + 1)..];
        if (AtomKindOf(atom) == "control" && rest.LastIndexOf(':') is > 0 and int last)
        {
            rest = rest[..last];
        }

        return ComputerUseSuccessCheck.Fold(rest).Trim();
    }

    /// <summary>
    /// Revision 3 of ronda 23 (s01, «en la calculadora decime el resultado»): the words with which a question asks for
    /// its answer («decime», «tell»), never what it asks about: «decime» shares the root of «decimal». Data
    /// «request_words» of answer_evidence_words.v1.json, one file with the mind (semantic.answer_evidence).
    /// </summary>
    internal static readonly Lazy<IReadOnlySet<string>> RequestWords = new(LoadRequestWords);

    private static HashSet<string> LoadRequestWords()
    {
        using Stream stream = typeof(ComputerUseMission).Assembly.GetManifestResourceStream("Baxy.App.AnswerEvidenceWords.json")
            ?? throw new InvalidOperationException("answer_evidence_words_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        return document.RootElement.GetProperty("request_words").EnumerateArray()
            .Select(word => word.GetString()).OfType<string>().ToHashSet(StringComparer.Ordinal);
    }

    /// <summary>
    /// Ronda 20b (v3-43): the content words of the question a goal carries (four letters or more), less those its place
    /// and the window's title already say: «abrir Opciones de energía…¿qué plan está activo?» on «Opciones de energía»
    /// keeps «plan», «esta», «activo»; never a word that asks for the answer (<see cref="RequestWords"/>). Empty for a
    /// goal without a question.
    /// </summary>
    internal static HashSet<string> QuestionContentWords(string? goal, JsonObject view)
    {
        var words = new HashSet<string>(StringComparer.Ordinal);
        if (!CarriesQuestion(goal))
        {
            return words;
        }

        int at = goal!.IndexOf(OperationFloor.QuestionMark, StringComparison.Ordinal);
        var said = new HashSet<string>(
            FoldedWords(goal[..at]).Concat(FoldedWords((string?)view["window"]?["title"])), StringComparer.Ordinal);
        foreach (string word in FoldedWords(goal[(at + OperationFloor.QuestionMark.Length)..]))
        {
            if (word.Length >= 4 && !said.Contains(word) && !RequestWords.Value.Contains(word))
            {
                words.Add(word);
            }
        }

        return words;

        static IEnumerable<string> FoldedWords(string? text) =>
            ComputerUseSuccessCheck.Fold(text).Split([' ', ':', ';', ',', '.', '?', '¿', '!', '¡'], StringSplitOptions.RemoveEmptyEntries);
    }

    /// <summary>The folded names the last verified act of the sub-goal made appear (<see cref="MarkAppeared"/>).</summary>
    internal static IReadOnlyCollection<string>? LastAppeared(JsonArray steps, int start)
    {
        if (steps.Count <= start || steps[^1] is not JsonObject last || last["appeared"] is not JsonArray appeared)
        {
            return null;
        }

        return appeared.Select(name => (string?)name).OfType<string>().ToHashSet(StringComparer.Ordinal);
    }

    /// <summary>Whether the goal carries the person's question (data «computerUse.questionMark»).</summary>
    internal static bool CarriesQuestion(string? goal) =>
        goal is not null && goal.Contains(OperationFloor.QuestionMark, StringComparison.Ordinal);
}

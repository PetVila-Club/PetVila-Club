from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import DomainError

from .models import Ticket, TicketMessage
from .services import open_ticket


class TicketMessageSerializer(serializers.ModelSerializer):
    from_team = serializers.SerializerMethodField()

    class Meta:
        model = TicketMessage
        fields = ["id", "body", "from_team", "created_at"]

    def get_from_team(self, obj) -> bool:
        return obj.author_id != obj.ticket.user_id


class TicketSerializer(serializers.ModelSerializer):
    protocol = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ["id", "protocol", "kind", "kind_label", "status", "status_label", "subject", "description",
                  "reference", "due_at", "resolution", "resolved_at", "messages", "created_at"]
        read_only_fields = ["status", "due_at", "resolution", "resolved_at"]

    def get_messages(self, obj):
        return TicketMessageSerializer(obj.messages.filter(internal=False), many=True).data


class TicketViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).prefetch_related("messages")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ticket = open_ticket(request.user, kind=data["kind"], subject=data["subject"], description=data["description"],
                             reference=data.get("reference", ""))
        return Response(TicketSerializer(ticket).data, status=201)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        body = (request.data.get("body") or "").strip()
        if not body:
            raise DomainError("Escreva uma mensagem.")
        if ticket.status in (Ticket.Status.CLOSED,):
            raise DomainError("Esta solicitação está encerrada. Abra uma nova, se precisar.")
        TicketMessage.objects.create(ticket=ticket, author=request.user, body=body[:4000])
        if ticket.status == Ticket.Status.WAITING_CUSTOMER:
            ticket.status = Ticket.Status.IN_PROGRESS
            ticket.save(update_fields=["status", "updated_at"])
        return Response(TicketSerializer(ticket).data)
